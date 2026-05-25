from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from django.db.models import Sum, Count, F, Q, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from api.models import Order, Expense, Product, OrderItem, Business, Party, Billing, BillingItem
from api.serializers import OrderSerializer


class BusinessSummaryView(APIView):
    def get(self, request, business_id=None):
        if not business_id:
            return Response({"error": "Business ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get date range from query params
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        scope = request.query_params.get('scope', 'full')
        cache_key = f"dashboard_summary:{business_id}:{scope}"

        if scope == 'dashboard':
            try:
                cached = cache.get(cache_key)
                if cached:
                    return Response(cached, status=status.HTTP_200_OK)
            except Exception:
                cached = None

        try:
            business = Business.objects.get(id=business_id)
            now = timezone.now()
            current_month = now.month
            current_year = now.year

            # ── Party Balances (To Receive / To Give) ──
            party_totals = Party.objects.filter(business_id=business_id).aggregate(
                to_receive=Sum(
                    'open_balance',
                    filter=Q(Category_type='Customer', open_balance__gt=0),
                ),
                to_give=Sum(
                    'open_balance',
                    filter=Q(Category_type='Supplier', open_balance__gt=0),
                ),
            )

            to_receive = party_totals.get('to_receive') or Decimal('0.00')
            to_give = party_totals.get('to_give') or Decimal('0.00')

            # ── Billing-based Sales & Purchase (current month) ──
            billings = Billing.objects.filter(business_id=business_id)

            monthly_totals = billings.filter(
                invoice_date__month=current_month,
                invoice_date__year=current_year,
            ).aggregate(
                monthly_sales=Sum(
                    'paid_amount',
                    filter=Q(transaction_type='Sales'),
                ),
                monthly_purchase=Sum(
                    'paid_amount',
                    filter=Q(transaction_type='Purchase'),
                ),
            )

            monthly_sales = monthly_totals.get(
                'monthly_sales') or Decimal('0.00')
            monthly_purchase = monthly_totals.get(
                'monthly_purchase') or Decimal('0.00')

            # ── Inventory Value ──
            products = Product.objects.filter(business_id=business_id)
            inventory_value = products.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F('unit_price') * F('quantity'),
                        output_field=DecimalField(
                            max_digits=20, decimal_places=2),
                    )
                )
            )['total'] or Decimal('0.00')

            # ── Cashflow Trends (last 7 days) ──
            seven_days_ago = now.date() - timedelta(days=6)

            daily_cashflow = billings.filter(
                invoice_date__gte=seven_days_ago
            ).annotate(
                day=TruncDate('invoice_date')
            ).values('day').annotate(
                inflow=Sum('total_amount', filter=Q(transaction_type='Sales')),
                outflow=Sum('total_amount', filter=Q(
                    transaction_type='Purchase')),
            ).order_by('day')

            # Build 7-day cashflow data
            cashflow_by_day = {
                str(item['day']): {
                    'inflow': float(item['inflow'] or 0),
                    'outflow': float(item['outflow'] or 0),
                }
                for item in daily_cashflow
            }

            cashflow_daily = []
            for i in range(7):
                day = seven_days_ago + timedelta(days=i)
                day_str = str(day)
                totals = cashflow_by_day.get(
                    day_str, {'inflow': 0, 'outflow': 0})
                cashflow_daily.append({
                    'date': day_str,
                    'label': day.strftime('%b %d'),
                    'inflow': totals['inflow'],
                    'outflow': totals['outflow'],
                })

            # ── Weekly cashflow (last 4 weeks) ──
            four_weeks_ago = now.date() - timedelta(weeks=4)
            weekly_cashflow = billings.filter(
                invoice_date__gte=four_weeks_ago
            ).annotate(
                week=TruncWeek('invoice_date')
            ).values('week').annotate(
                inflow=Sum('total_amount', filter=Q(transaction_type='Sales')),
                outflow=Sum('total_amount', filter=Q(
                    transaction_type='Purchase')),
            ).order_by('week')

            weekly_by_start = {}
            for item in weekly_cashflow:
                week_key = item['week'].date() if hasattr(
                    item['week'], 'date') else item['week']
                weekly_by_start[str(week_key)] = {
                    'inflow': float(item['inflow'] or 0),
                    'outflow': float(item['outflow'] or 0),
                }

            cashflow_weekly = []
            for i in range(4):
                week_start = four_weeks_ago + timedelta(weeks=i)
                week_key = str(week_start)
                totals = weekly_by_start.get(
                    week_key, {'inflow': 0, 'outflow': 0})
                cashflow_weekly.append({
                    'label': f'Week {i+1}',
                    'inflow': totals['inflow'],
                    'outflow': totals['outflow'],
                })

            # ── Monthly cashflow (last 6 months) ──
            month_starts = []
            for i in range(6):
                month_offset = 5 - i
                m = now.month - month_offset
                y = now.year
                while m <= 0:
                    m += 12
                    y -= 1
                month_starts.append(timezone.datetime(y, m, 1).date())

            monthly_cashflow = billings.filter(
                invoice_date__gte=month_starts[0]
            ).annotate(
                month=TruncMonth('invoice_date')
            ).values('month').annotate(
                inflow=Sum('total_amount', filter=Q(transaction_type='Sales')),
                outflow=Sum('total_amount', filter=Q(
                    transaction_type='Purchase')),
            ).order_by('month')

            monthly_by_start = {}
            for item in monthly_cashflow:
                month_key = item['month'].date() if hasattr(
                    item['month'], 'date') else item['month']
                monthly_by_start[str(month_key)] = {
                    'inflow': float(item['inflow'] or 0),
                    'outflow': float(item['outflow'] or 0),
                }

            cashflow_monthly = []
            for month_start in month_starts:
                import calendar
                month_name = calendar.month_abbr[month_start.month]
                totals = monthly_by_start.get(
                    str(month_start), {'inflow': 0, 'outflow': 0})
                cashflow_monthly.append({
                    'label': month_name,
                    'inflow': totals['inflow'],
                    'outflow': totals['outflow'],
                })

            dashboard_payload = {
                "dashboard": {
                    "to_receive": float(to_receive),
                    "to_give": float(to_give),
                    "monthly_sales": float(monthly_sales),
                    "monthly_purchase": float(monthly_purchase),
                    "inventory_value": float(inventory_value),
                    "current_month": now.strftime('%B'),
                    "current_month_short": now.strftime('%b').upper(),
                },
                "cashflow": {
                    "daily": cashflow_daily,
                    "weekly": cashflow_weekly,
                    "monthly": cashflow_monthly,
                },
            }

            if scope == 'dashboard':
                try:
                    cache.set(cache_key, dashboard_payload, 30)
                except Exception:
                    pass
                return Response(dashboard_payload, status=status.HTTP_200_OK)

            # ── Sales Summary from Orders (legacy) ──
            orders = Order.objects.filter(business_id=business_id)
            if start_date_str:
                orders = orders.filter(created_at__date__gte=start_date_str)
            if end_date_str:
                orders = orders.filter(created_at__date__lte=end_date_str)

            order_totals = orders.aggregate(
                total_sales=Sum('total_amount'),
                order_count=Count('id'),
            )
            total_sales = order_totals.get('total_sales') or 0
            order_count = order_totals.get('order_count') or 0

            # Expenses Summary
            expenses = Expense.objects.filter(user=business.user)
            if start_date_str:
                expenses = expenses.filter(date__gte=start_date_str)
            if end_date_str:
                expenses = expenses.filter(date__lte=end_date_str)

            total_expenses = expenses.aggregate(
                total=Sum('amount'))['total'] or 0

            # Low stock count
            low_stock_count = products.filter(is_low_stock=True).count()

            # Top Selling Products
            top_products = OrderItem.objects.filter(order__business_id=business_id) \
                .values('product_id__product_name') \
                .annotate(total_qty=Sum('quantity'), total_revenue=Sum('total_price')) \
                .order_by('-total_qty')[:5]

            # Sales by Category
            sales_by_category = OrderItem.objects.filter(order__business_id=business_id) \
                .values('product_id__category__name') \
                .annotate(value=Sum('total_price')) \
                .order_by('-value')

            # Top Customers
            top_customers = Order.objects.filter(business_id=business_id, customer_id__isnull=False) \
                .values('customer_id__name') \
                .annotate(total_spent=Sum('total_amount'), order_count=Count('id')) \
                .order_by('-total_spent')[:5]

            # All-time billing totals
            billing_totals = billings.aggregate(
                total_billing_sales=Sum(
                    'total_amount', filter=Q(transaction_type='Sales')
                ),
                total_billing_purchases=Sum(
                    'total_amount', filter=Q(transaction_type='Purchase')
                ),
            )

            total_billing_sales = billing_totals.get(
                'total_billing_sales') or 0
            total_billing_purchases = billing_totals.get(
                'total_billing_purchases') or 0

            return Response({
                **dashboard_payload,
                "dashboard": {
                    **dashboard_payload["dashboard"],
                    "total_billing_sales": float(total_billing_sales),
                    "total_billing_purchases": float(total_billing_purchases),
                },
                "summary": {
                    "total_sales": float(total_sales or 0),
                    "order_count": order_count,
                    "total_expenses": float(total_expenses or 0),
                    "net_profit": float(total_sales or 0) - float(total_expenses or 0),
                    "total_stock_value": float(inventory_value or 0),
                    "low_stock_count": low_stock_count,
                },
                "top_products": [
                    {
                        "name": item['product_id__product_name'],
                        "quantity": item['total_qty'],
                        "revenue": float(item['total_revenue'] or 0)
                    } for item in top_products
                ],
                "category_distribution": [
                    {
                        "name": item['product_id__category__name'] or "Uncategorized",
                        "value": float(item['value'] or 0)
                    } for item in sales_by_category
                ],
                "top_customers": [
                    {
                        "name": item['customer_id__name'],
                        "spent": float(item['total_spent'] or 0),
                        "orders": item['order_count']
                    } for item in top_customers
                ]
            }, status=status.HTTP_200_OK)

        except Business.DoesNotExist:
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
