from .models import Reminder
from .serializers import ReminderSerializer
import json
import traceback
import random
import logging
from decimal import Decimal
from datetime import timedelta

from django.db.models import Prefetch
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db import models
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.core.mail import send_mail
import random
from .models import Business, Counter, Customer, Department, Employee, ForgetPasswordOTP, Party, Product, StockAlert, Supplier, Expense, Billing, BillingItem, Shift, Order, OrderStatus, AprioriRule, EmployeeSchedule, Skill, EmployeeSkill, PaymentMethod
from .serializers import CounterSerializer, ProductSerializer, PartySerializer, CustomerSerializer, StockAlertSerializer, SupplierSerializer, ExpenseSerializer, BillingSerializer, BillingItemSerializer, EmployeeSerializer, SkillSerializer, EmployeeSkillSerializer, ShiftSerializer, SchedulerRequestSerializer, OrderSerializer, AprioriRuleSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from datetime import timedelta
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import (
    Business, Counter, Customer, Department, Employee, ForgetPasswordOTP,
    Party, Product, StockAlert, Supplier, Expense, Billing, BillingItem,
    Shift, Order, OrderStatus, AprioriRule, EmployeeSchedule, Skill,
    EmployeeSkill, PaymentTransaction, OrderItem, ExpenseCategory
)
from api.serializers import (
    CounterSerializer, ProductSerializer, PartySerializer,
    StockAlertSerializer, ExpenseSerializer, BillingSerializer,
    BillingItemSerializer, EmployeeSerializer, SkillSerializer, EmployeeSkillSerializer,
    ShiftSerializer, SchedulerRequestSerializer, OrderSerializer,
    AprioriRuleSerializer, PaymentTransactionSerializer
)
from api.tasks import send_otp_email
from api.services.productService import check_low_stock_and_alert, create_product, get_product
from api.services.employeeServices import get_all_employees, create_employee
from api.services.scheduler import WSMStaffScheduler
from api.services.orderServices import get_order, create_order
from api.utils.apiriori_utils import get_reorder_suggestions, run_apriori, save_rules_to_db, create_apriori_stock_alerts, resolve_apriori_alerts


# OTP Expiry Time (5 minutes)
OTP_EXPIRY_TIME = timedelta(minutes=5)

# Inactivity period after which a party is considered inactive (e.g., 90 days)
PARTY_INACTIVITY_PERIOD = timedelta(days=90)

logger = logging.getLogger(__name__)


@login_required
def inventory_suggestions(request):
    """
    Returns reorder suggestions based on Apriori rules
    for the logged-in user's business.
    """
    business = Business.objects.filter(user=request.user).first()
    if not business:
        return JsonResponse(
            {"error": "No business found for this user"},
            status=404
        )

    suggestions = get_reorder_suggestions(business_id=business.id)

    return JsonResponse(suggestions, safe=False)


@login_required
def association_rules_view(request):
    """
    Returns all discovered association rules for the business.
    Useful for displaying in an admin/analytics dashboard.
    """
    business = Business.objects.filter(user=request.user).first()
    if not business:
        return JsonResponse(
            {"error": "No business found for this user"},
            status=404
        )

    rules, message = run_apriori(business_id=business.id)

    if rules is None:
        return JsonResponse({"error": message})

    rules_list = []
    for _, rule in rules.iterrows():
        rules_list.append({
            'if_customer_buys': list(rule['antecedents']),
            'they_also_buy': list(rule['consequents']),
            'confidence': f"{rule['confidence']:.0%}",
            'lift': round(rule['lift'], 2),
            'support': round(rule['support'], 2)
        })

    return JsonResponse({
        "message": message,
        "rules": rules_list
    })


def _build_invoice_number(order_id):
    base = f"ORD-{order_id}"
    invoice_number = base
    suffix = 1
    while Billing.objects.filter(invoice_number=invoice_number).exists():
        invoice_number = f"{base}-{suffix}"
        suffix += 1
    return invoice_number


def _sync_billing_for_completed_counter_order(order_obj, user):
    # Only counter orders should auto-generate billing on completion.
    if not order_obj.counter_id:
        return None

    # Fallback if user is anonymous (OrderView has AllowAny)
    if not user or not user.is_authenticated:
        from django.contrib.auth.models import User
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            # Fallback to the user who owns the business
            business = order_obj.business_id
            user = User.objects.filter(id=business.owner_id).first(
            ) if hasattr(business, 'owner_id') else None

    customer = order_obj.customer_id
    party = customer.party if customer and hasattr(customer, 'party') else None
    sub_total = sum(
        (item.total_price for item in order_obj.items.all()), Decimal('0.00'))
    total_amount = order_obj.total_amount or Decimal('0.00')

    defaults = {
        'user': user,
        'business_id_id': order_obj.business_id_id,
        'invoice_number': _build_invoice_number(order_obj.id),
        'invoice_date': timezone.now().date(),
        'due_date': timezone.now().date(),
        'transaction_type': 'Sales',
        'payment_method': customer.payment_method if customer else None,
        'invoice_status': 'Pending',
        'party': party,
        'phone': customer.phone_no if customer else None,
        'address': customer.address if customer else None,
        'notes': f'Auto-generated from counter order #{order_obj.id}',
        'paid_amount': Decimal('0.00'),
        'due_amount': total_amount,
        'total_amount': total_amount,
        'discount': order_obj.discount or Decimal('0.00'),
        'tax': order_obj.tax or Decimal('0.00'),
        'sub_total': sub_total,
    }

    billing, created = Billing.objects.get_or_create(
        order=order_obj, defaults=defaults)

    if not created:
        invoice_number = billing.invoice_number or _build_invoice_number(
            order_obj.id)
        for field, value in defaults.items():
            setattr(billing, field, value)
        billing.invoice_number = invoice_number
        billing.save()

    BillingItem.objects.filter(billing=billing).delete()
    billing_items = [
        BillingItem(
            billing=billing,
            item=item.product_id,
            quantity=item.quantity,
            rate=item.unit_price,
            discount_percentage=Decimal('0.00'),
            tax_percentage=Decimal('13.00'),
            total_price=item.total_price,
        )
        for item in order_obj.items.all()
    ]
    if billing_items:
        BillingItem.objects.bulk_create(billing_items)

    return billing


def _dispatch_otp_email(email, otp):
    """Try async OTP dispatch first, then fall back to sync send."""
    try:
        send_otp_email.delay(email, otp)
        return True
    except Exception as exc:
        logger.warning("Async OTP dispatch failed for %s: %s", email, exc)

    # Fallback keeps auth flow usable when Celery/Redis is unavailable in local dev.
    try:
        return bool(send_otp_email(email, otp))
    except Exception as exc:
        logger.error("Fallback OTP send failed for %s: %s", email, exc)
        return False


def get_tokens_for_user(user):
    """
    Generate JWT tokens for a user.
    """
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get('username', '').strip()
        email = request.data.get('email', '').lower()
        password = request.data.get('password')
        phone_no = request.data.get('phone_no', '').strip()
        business_name = request.data.get('business_name', '').strip()

        if not username or not email or not password:
            return Response(
                {'error': 'Username, email and password are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_user = User.objects.filter(email=email).first()
        existing_business = Business.objects.filter(
            user=existing_user).first() if existing_user else None

        if existing_user and existing_business and existing_business.is_verified:
            return Response({'error': 'User with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exclude(email=email).exists():
            return Response({'error': 'Username is already taken.'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate OTP
        otp = str(random.randint(100000, 999999))

        try:
            with transaction.atomic():
                if existing_user:
                    user = existing_user
                    user.username = username
                    user.email = email
                    user.set_password(password)
                    user.save()

                    business = Business.objects.filter(
                        user=user).order_by('-created_at').first()
                    if business:
                        business.business_name = business_name or business.business_name
                        business.business_email = email
                        business.business_phone_no = phone_no
                        business.otp = otp
                        business.otp_created_at = timezone.now()
                        business.is_verified = False
                        business.save()
                    else:
                        Business.objects.create(
                            user=user,
                            business_name=business_name or f"{username}'s Business",
                            business_email=email,
                            business_phone_no=phone_no,
                            otp=otp,
                            otp_created_at=timezone.now(),
                            is_verified=False,
                        )
                else:
                    user = User.objects.create_user(
                        username=username, email=email, password=password)
                    Business.objects.create(
                        user=user,
                        business_name=business_name,
                        business_email=email,
                        business_phone_no=phone_no,
                        otp=otp,
                        otp_created_at=timezone.now(),
                        is_verified=False
                    )
        except IntegrityError:
            return Response({'error': 'Username or email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        if not _dispatch_otp_email(email, otp):
            return Response(
                {'error': 'Account created, but OTP delivery failed. Please try again in a moment.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({'message': 'User created successfully. Please verify the OTP sent to your email.'},
                        status=status.HTTP_201_CREATED)


class VerifySignupOtpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        otp_provided = request.data.get('otp', '').strip()

        try:
            user = User.objects.get(email=email.lower())
            business = Business.objects.filter(
                user=user).order_by('-created_at').first()
            if not business:
                return Response({'error': 'Business not found for this user'}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check OTP expiry
        if not business.otp or not business.otp_created_at:
            return Response({'error': 'No OTP found'}, status=status.HTTP_400_BAD_REQUEST)

        if timezone.now() > business.otp_created_at + OTP_EXPIRY_TIME:
            return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify OTP
        if str(business.otp) == str(otp_provided):
            business.is_verified = True
            business.otp = None
            business.otp_created_at = None
            business.save()
            return Response({'message': 'Signup OTP verified successfully!'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')

        try:
            user = User.objects.get(email=email)
            if not user.check_password(password):
                return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Save OTP in business with timestamp
        business = Business.objects.filter(
            user=user).order_by('-created_at').first()
        if not business:
            business = Business.objects.create(
                user=user,
                business_name=f"{user.username}'s Business",
                business_email=user.email,
            )

        business.save()
        tokens = get_tokens_for_user(user)

        return Response({
            'message': 'Login successful',
            'tokens': tokens,
            'business_id': business.id
        }, status=status.HTTP_200_OK)


class ApiProductView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, business_id=None, product_id=None, **kwargs):
        product_id = product_id or request.query_params.get('id')
        business_id = business_id or request.query_params.get('business_id')

        if not business_id:
            return Response({'message': 'Business ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if product_id:
                data = get_product(product_id=product_id,
                                   business_id=business_id)
                return Response(data, status=status.HTTP_200_OK)

            if business_id:
                data = get_product(business_id=business_id)
                return Response(data, status=status.HTTP_200_OK)

            return Response({'message': 'Product ID or Business ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, business_id=None):
        data = request.data.copy()
        data['business_id'] = business_id

        if not business_id:
            return Response({'error': 'Business ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        if Product.objects.filter(business_id=business_id, product_name=data['product_name']).exists():
            return Response({'error': 'You already have a product with this name.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = create_product(data)
            # Clear dashboard cache
            from django.core.cache import cache
            cache.delete(f"dashboard_summary:{business_id}:dashboard")
            return Response(result, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, business_id=None, product_id=None):
        if not business_id:
            return Response({'error': 'Business ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not product_id:
            return Response({'error': 'Product ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Convert product_id to an integer
            product_id = int(product_id)

            # Ensure the product exists and belongs to the business
            product = Product.objects.get(
                id=product_id, business_id=business_id)
        except ValueError:
            return Response({'error': 'Invalid Product ID'}, status=status.HTTP_400_BAD_REQUEST)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found or you do not have permission to edit it.'}, status=status.HTTP_404_NOT_FOUND)

        # Update the product with the provided data
        # Use partial=True for partial updates
        serializer = ProductSerializer(
            product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # Clear dashboard cache
            from django.core.cache import cache
            cache.delete(f"dashboard_summary:{business_id}:dashboard")
            return Response({'message': 'Product updated successfully!',
                             'product': serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, business_id=None, product_id=None, **kwargs):
        if not business_id:
            return Response({'error': 'Business ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Get the product ID from the query parameters or URL
        product_id = product_id or request.query_params.get('id')
        if not product_id:
            return Response({'error': 'Product ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Ensure the product belongs to the business
            product = Product.objects.get(
                id=product_id, business_id=business_id)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found or you do not have permission to delete it.'}, status=status.HTTP_404_NOT_FOUND)

        product.delete()
        # Clear dashboard cache
        from django.core.cache import cache
        cache.delete(f"dashboard_summary:{business_id}:dashboard")
        return Response({'message': 'Product deleted successfully!'}, status=status.HTTP_200_OK)


class ApiPartyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id=None, party_id=None):
        if not business_id:
            business_id = request.query_params.get('business_id')
        if not business_id:
            return Response({'error': 'Business ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        if party_id:
            try:
                party = Party.objects.select_related('business_id').get(
                    id=party_id, business_id=business_id)
                serializer = PartySerializer(party)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Party.DoesNotExist:
                return Response({'error': 'Party not found'}, status=status.HTTP_404_NOT_FOUND)

        category_type = request.query_params.get('category_type')
        parties = Party.objects.filter(business_id=business_id).select_related(
            'business_id').order_by('-id')
        if category_type:
            parties = parties.filter(Category_type=category_type)

        paginator = PageNumberPagination()
        paginator.page_size = 10
        result_page = paginator.paginate_queryset(parties, request)
        serializer = PartySerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, business_id=None):
        if not business_id:
            business_id = request.query_params.get('business_id')
        if not business_id:
            return Response({'error': 'Business ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data.copy()
        data['business_id'] = business_id

        category = data.get('Category_type')
        if category not in ['Customer', 'Supplier']:
            return Response({"error": "Invalid Category. Must be 'Customer' or 'Supplier'"},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = PartySerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': f'{category} created successfully!',
                'party': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, business_id=None, party_id=None):
        if not business_id:
            business_id = request.query_params.get('business_id')
        if not party_id:
            party_id = request.query_params.get('id')

        if not business_id or not party_id:
            return Response({'error': 'Business ID and Party ID are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            party = Party.objects.get(id=party_id, business_id=business_id)
        except Party.DoesNotExist:
            return Response({'error': 'Party not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PartySerializer(party, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Party updated successfully!',
                'party': serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, business_id=None, party_id=None):
        if not business_id:
            business_id = request.query_params.get('business_id')
        if not party_id:
            party_id = request.query_params.get('id')

        if not business_id or not party_id:
            return Response({'error': 'Business ID and Party ID are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            party = Party.objects.get(id=party_id, business_id=business_id)
        except Party.DoesNotExist:
            return Response({'error': 'Party not found'}, status=status.HTTP_404_NOT_FOUND)

        party.delete()
        return Response({'message': 'Party deleted successfully!'}, status=status.HTTP_200_OK)


class ApiPaymentTransactionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id=None, transaction_id=None):
        if not business_id:
            return Response({'error': 'Business ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        if transaction_id:
            try:
                txn = PaymentTransaction.objects.select_related(
                    'party', 'business_id', 'payment_method'
                ).get(id=transaction_id, business_id=business_id)
                serializer = PaymentTransactionSerializer(txn)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except PaymentTransaction.DoesNotExist:
                return Response({'error': 'Transaction not found'}, status=status.HTTP_404_NOT_FOUND)

        party_id = request.query_params.get('party_id')
        txns = PaymentTransaction.objects.filter(business_id=business_id).select_related(
            'party', 'business_id', 'payment_method'
        ).order_by('-date', '-created_at')

        if party_id:
            txns = txns.filter(party_id=party_id)

        paginator = PageNumberPagination()
        paginator.page_size = 10
        result_page = paginator.paginate_queryset(txns, request)
        serializer = PaymentTransactionSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, business_id=None):
        if not business_id:
            return Response({'error': 'Business ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data.copy()
        data['business_id'] = business_id

        serializer = PaymentTransactionSerializer(data=data)
        if serializer.is_valid():
            with transaction.atomic():
                txn = serializer.save()
                # Update party balance
                party = txn.party
                if txn.transaction_type == 'payment_in':
                    party.open_balance -= txn.amount
                elif txn.transaction_type == 'payment_out':
                    party.open_balance += txn.amount
                party.save()

            return Response({
                'message': 'Transaction recorded successfully!',
                'transaction': PaymentTransactionSerializer(txn).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, business_id=None, transaction_id=None):
        if not business_id or not transaction_id:
            return Response({'error': 'Business ID and Transaction ID are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            txn = PaymentTransaction.objects.get(
                id=transaction_id, business_id=business_id)
        except PaymentTransaction.DoesNotExist:
            return Response({'error': 'Transaction not found'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            party = txn.party
            if txn.transaction_type == 'payment_in':
                party.open_balance += txn.amount
            elif txn.transaction_type == 'payment_out':
                party.open_balance -= txn.amount
            party.save()
            txn.delete()

        return Response({'message': 'Transaction deleted successfully!'}, status=status.HTTP_200_OK)


class ApiExpenseView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        paginator = PageNumberPagination()
        paginator.page_size = 10
        expenses = Expense.objects.filter(user=request.user).select_related(
            'user', 'business_id', 'category'
        )
        result_page = paginator.paginate_queryset(expenses, request)
        serializer = ExpenseSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, *args, **kwargs):
        expense_data = request.data.copy()
        expense_data['user'] = request.user.id

        serializer = ExpenseSerializer(data=expense_data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Expense created successfully!',
                             'expense': serializer.data}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        expense_id = request.query_params.get('id')
        if not expense_id:
            return Response({'error': 'Expense ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            expense_id = int(expense_id)
            expense = Expense.objects.get(id=expense_id, user=request.user)
        except ValueError:
            return Response({'error': 'Invalid Expense ID'}, status=status.HTTP_400_BAD_REQUEST)
        except Expense.DoesNotExist:
            return Response({'error': 'Expense not found or you do not have permission to edit it.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ExpenseSerializer(
            expense, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Expense updated successfully!',
                             'expense': serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        expense_id = request.query_params.get('id')
        if not expense_id:
            return Response({'error': 'Expense ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            expense = Expense.objects.get(id=expense_id, user=request.user)
        except Expense.DoesNotExist:
            return Response({'error': 'Expense not found or you do not have permission to delete it.'}, status=status.HTTP_404_NOT_FOUND)

        expense.delete()
        return Response({'message': 'Expense deleted successfully!'}, status=status.HTTP_200_OK)


class ApiBillingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id=None, billing_id=None):
        if not business_id:
            return Response({'error': 'Business ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        if billing_id:
            try:
                billing = Billing.objects.select_related(
                    'party', 'user', 'business_id', 'payment_method', 'order'
                ).prefetch_related('items__item').get(
                    id=billing_id, business_id=business_id)
                serializer = BillingSerializer(billing)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Billing.DoesNotExist:
                return Response({'error': 'Billing record not found'}, status=status.HTTP_404_NOT_FOUND)

        status_filter = request.query_params.get('status')
        billings = Billing.objects.filter(business_id=business_id).select_related(
            'party').prefetch_related('items__item').order_by('-id')

        if status_filter:
            billings = billings.filter(invoice_status__iexact=status_filter)

        paginator = PageNumberPagination()
        paginator.page_size = 10
        result_page = paginator.paginate_queryset(billings, request)
        serializer = BillingSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, business_id=None):
        if not business_id:
            return Response({'error': 'Business ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data.copy()
        data['business_id'] = business_id
        data['user'] = request.user.id
        items_data = data.pop('items', [])

        if not items_data:
            return Response({'error': 'At least one billing item is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Handle payment method string to object conversion
                pm_name = data.get('payment_method')
                if pm_name and isinstance(pm_name, str):
                    pm_obj, _ = PaymentMethod.objects.get_or_create(
                        method_name=pm_name)
                    # SlugRelatedField uses name
                    data['payment_method'] = pm_obj.method_name

                serializer = BillingSerializer(data=data)
                if not serializer.is_valid():
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                billing = serializer.save()

                for item_data in items_data:
                    item_data['billing'] = billing.id
                    # Ensure rate and total_price are handled if sent from frontend
                    if 'rate' not in item_data and 'price' in item_data:
                        item_data['rate'] = item_data['price']

                    item_serializer = BillingItemSerializer(data=item_data)
                    if not item_serializer.is_valid():
                        raise ValueError(str(item_serializer.errors))

                    billing_item = item_serializer.save()

                    # Stock Management
                    product = billing_item.item
                    qty = billing_item.quantity
                    if billing.transaction_type == 'Sales':
                        product.quantity -= qty
                    elif billing.transaction_type == 'Purchase':
                        product.quantity += qty
                    product.save()

                # Update party balance for Unpaid invoices
                if billing.party and billing.invoice_status == 'Unpaid':
                    party = billing.party
                    due = billing.total_amount
                    if billing.transaction_type == 'Sales':
                        party.open_balance += due
                    elif billing.transaction_type == 'Purchase':
                        party.open_balance -= due
                    party.save()

                # Clear dashboard cache
                from django.core.cache import cache
                cache.delete(f"dashboard_summary:{business_id}:dashboard")

                return Response({
                    'message': 'Billing created successfully!',
                    'billing': BillingSerializer(billing).data
                }, status=status.HTTP_201_CREATED)

        except ValueError as ve:
            return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating billing: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, business_id=None):
        if not business_id:
            return Response({'error': 'Business ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        billing_id = request.query_params.get('id')
        if not billing_id:
            return Response({'error': 'Billing ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            billing_id = int(billing_id)
            billing = Billing.objects.get(id=billing_id, business_id=business_id)
        except ValueError:
            return Response({'error': 'Invalid Billing ID'}, status=status.HTTP_400_BAD_REQUEST)
        except Billing.DoesNotExist:
            return Response({'error': 'Billing not found or you do not have permission to edit it.'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            serializer = BillingSerializer(
                billing, data=request.data, partial=True)
            if serializer.is_valid():
                billing = serializer.save()

                # Handle items update
                items_data = request.data.get('items', [])
                if items_data:
                    # Delete old items
                    BillingItem.objects.filter(billing=billing).delete()

                    # Create new items
                    for item_data in items_data:
                        item_data['billing'] = billing.id
                        item_serializer = BillingItemSerializer(data=item_data)
                        if item_serializer.is_valid():
                            item_serializer.save()
                        else:
                            return Response(item_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                # Clear dashboard cache
                from django.core.cache import cache
                cache.delete(f"dashboard_summary:{business_id}:dashboard")

                return Response({'message': 'Billing updated successfully!',
                                 'billing': BillingSerializer(billing).data}, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, business_id=None):
        if not business_id:
            return Response({'error': 'Business ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        billing_id = request.query_params.get('id')
        if not billing_id:
            return Response({'error': 'Billing ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            billing = Billing.objects.get(id=billing_id, business_id=business_id)
        except Billing.DoesNotExist:
            return Response({'error': 'Billing not found or you do not have permission to delete it.'}, status=status.HTTP_404_NOT_FOUND)

        billing.delete()

        # Clear dashboard cache
        from django.core.cache import cache
        cache.delete(f"dashboard_summary:{business_id}:dashboard")

        return Response({'message': 'Billing deleted successfully!'}, status=status.HTTP_200_OK)


class ForgetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Generate OTP
        otp = str(random.randint(100000, 999999))

        # Create ForgetPasswordOTP entry
        forget_password_otp = ForgetPasswordOTP.objects.create(
            user=user,
            otp=otp,
            otp_created_at=timezone.now(),
            is_verify=False
        )

        # Send OTP to the user's email
        send_otp_email.delay(email, otp)

        return Response({'message': 'OTP sent to your email. Please verify to reset your password.'},
                        status=status.HTTP_200_OK)


class VerifyForgetPasswordOtpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        otp_provided = request.data.get('otp', '').strip()

        try:
            user = User.objects.get(email=email)
            forget_password_otp = ForgetPasswordOTP.objects.filter(
                user=user).latest('otp_created_at')
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except ForgetPasswordOTP.DoesNotExist:
            return Response({'error': 'No OTP found for this user'}, status=status.HTTP_400_BAD_REQUEST)

        # Check OTP expiry
        if not forget_password_otp.otp or not forget_password_otp.otp_created_at:
            return Response({'error': 'No OTP found'}, status=status.HTTP_400_BAD_REQUEST)

        if timezone.now() > forget_password_otp.otp_created_at + OTP_EXPIRY_TIME:
            return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify OTP
        if str(forget_password_otp.otp) == str(otp_provided):
            forget_password_otp.is_verify = True
            forget_password_otp.save()
            return Response({'message': 'Forget Password OTP verified successfully!'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        new_password = request.data.get('new_password')

        try:
            user = User.objects.get(email=email)
            forget_password_otp = ForgetPasswordOTP.objects.filter(
                user=user).latest('otp_created_at')
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except ForgetPasswordOTP.DoesNotExist:
            return Response({'error': 'No OTP found for this user'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if OTP was verified
        if forget_password_otp.is_verify == False:
            return Response({'error': 'OTP not verified'}, status=status.HTTP_400_BAD_REQUEST)

        # Reset the password
        user.set_password(new_password)
        user.save()

        # Optionally, delete the OTP entry after successful password reset
        forget_password_otp.delete()

        return Response({'message': 'Password reset successfully!'}, status=status.HTTP_200_OK)


class EmployeeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, business_id=None, employee_id=None):
        try:
            if not business_id:
                return Response({"error": "Business ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)
            data = get_all_employees(business_id, employee_id)
            return data
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, business_id=None):
        try:
            if not business_id:
                return Response({"error": "Business ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)
            result = create_employee(business_id, request.data)
            return result
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, business_id=None, employee_id=None):
        try:
            if not business_id or not employee_id:
                return Response({"error": "Business ID and Employee ID are required in the url"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                employee_obj = Employee.objects.get(
                    id=employee_id, business_id=business_id)
            except Employee.DoesNotExist:
                return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

            data = request.data
            # Ensure department exists if provided
            dept_name = data.get('department')
            if dept_name and isinstance(dept_name, str):
                Department.objects.get_or_create(
                    name=dept_name, business_id_id=business_id)

            serializer = EmployeeSerializer(
                employee_obj, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'Employee updated successfully', 'data': serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, business_id=None, employee_id=None):
        try:
            if not business_id or not employee_id:
                return Response({"error": "Business ID and Employee ID are required in the url"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                employee_obj = Employee.objects.get(
                    id=employee_id, business_id=business_id)
            except Employee.DoesNotExist:
                return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

            employee_obj.delete()
            return Response({'message': 'Employee deleted successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DepartmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id=None):
        try:
            if not business_id:
                return Response({"error": "Business ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            departments = Department.objects.filter(
                models.Q(business_id=business_id) | models.Q(business_id__isnull=True))
            # If no departments exist for this business, you might want to return some defaults or an empty list
            data = [{"id": d.id, "name": d.name} for d in departments]
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, business_id=None):
        try:
            if not business_id:
                return Response({"error": "Business ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            name = request.data.get("name")
            if not name:
                return Response({"error": "Name is required"}, status=status.HTTP_400_BAD_REQUEST)

            dept, created = Department.objects.get_or_create(
                name=name, business_id_id=business_id)
            return Response({"id": dept.id, "name": dept.name, "created": created}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StaffSchedulerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            serializer = SchedulerRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )

            business_id = serializer.validated_data['business_id']
            shift_ids = serializer.validated_data['shift_ids']
            max_hours = serializer.validated_data.get('max_hours_per_week', 40)
            apply = serializer.validated_data.get('apply_schedule', False)

            # Check business exists
            try:
                business = Business.objects.get(id=business_id)
            except Business.DoesNotExist:
                return Response(
                    {'error': 'Business not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get shifts
            shifts = Shift.objects.filter(
                id__in=shift_ids,
                business_id=business_id
            )

            if not shifts.exists():
                return Response(
                    {'error': 'No valid shifts found'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            weights = serializer.validated_data.get('weights')

            # Run WSM scheduler
            scheduler = WSMStaffScheduler(
                business_id, shifts, weights, max_hours)
            schedule, unscheduled = scheduler.schedule_shifts_greedy()
            schedule_summary = scheduler.get_schedule_summary()

            if apply:
                result = scheduler.apply_schedule()
            else:
                result = {
                    'scheduled_count':   len(schedule),
                    'unscheduled_count': len(unscheduled),
                    'total_shifts':      shifts.count(),
                    'success_rate':      f"{(len(schedule) / shifts.count() * 100):.2f}%"
                    if shifts.count() else "0%",
                    'assignments': [
                        {
                            'shift_id': item['shift'].id,
                            'assigned': item['employee'].name,
                            'score':    item['score'],
                            'rankings': [
                                {'name': r[0].name, 'score': r[1]} for r in item['rankings']
                            ]
                        } for item in schedule
                    ]
                }

            return Response({
                'status':            'success',
                'scheduling_result': result,
                'schedule_summary':  schedule_summary,
                'applied':           apply,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request, business_id=None, *args, **kwargs):
        try:
            if not business_id:
                return Response(
                    {'error': 'business_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ✅ FIXED — also check ownership on GET
            if not Business.objects.filter(
                id=business_id,
                user_id=request.user.id
            ).exists():
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )

            employee_id = request.query_params.get('employee_id')

            shifts = Shift.objects.filter(
                business_id=business_id,
                assigned_employee_id=employee_id
            ).select_related(
                'business_id', 'assigned_employee', 'required_skill'
            ) if employee_id else Shift.objects.filter(
                business_id=business_id
            ).select_related(
                'business_id', 'assigned_employee', 'required_skill'
            )

            serializer = ShiftSerializer(shifts, many=True)
            return Response({
                'status': 'success',
                'data':   serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OrderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id=None, order_id=None, counter_id=None, customer_id=None):
        try:
            if not business_id:
                return Response({"error": "Business ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)

            # Extract status from query params
            status_name = request.query_params.get('status')

            # Call get_order with all possible filter params from URL
            data = get_order(
                business_id=business_id,
                order_id=order_id,
                counter_id=counter_id,
                customer_id=customer_id,
                status_name=status_name
            )
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, business_id=None, counter_id=None, customer_id=None):
        try:
            data = request.data

            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    return Response({"error": "Invalid JSON payload. Expected an object."}, status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(data, dict):
                if hasattr(data, 'dict'):
                    data = data.dict()
                elif hasattr(data, 'copy'):
                    data = data.copy()
                else:
                    data = dict(data)

            if business_id is not None:
                data['business_id'] = business_id
            if counter_id is not None:
                data['counter_id'] = counter_id
            if customer_id is not None:
                data['customer_id'] = customer_id
            if not business_id:
                return Response({"error": "Business ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)
            result = create_order(data, business_id, counter_id, customer_id)
            return result
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, business_id=None, order_id=None):
        try:
            if not business_id or not order_id:
                return Response({"error": "Business ID and Order ID are required in the url"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                order_obj = Order.objects.get(
                    id=order_id, business_id=business_id)
            except Order.DoesNotExist:
                return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

            previous_status_name = (order_obj.order_status.name.lower()
                                    if order_obj.order_status else "")

            data = request.data
            serializer = OrderSerializer(
                order_obj, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()

                # Optimized: Re-fetch with pre-fetches before sync to avoid N+1
                order_obj = Order.objects.select_related(
                    'order_status', 'customer_id', 'business_id', 'counter'
                ).prefetch_related(
                    Prefetch('items', queryset=OrderItem.objects.select_related(
                        'status', 'product_id'))
                ).get(id=order_obj.id)

                current_status_name = (order_obj.order_status.name.lower()
                                       if order_obj.order_status else "")
                billing = None
                if current_status_name in {'completed', 'complete', 'paid'}:
                    billing = _sync_billing_for_completed_counter_order(
                        order_obj, request.user)

                response_data = {
                    'message': 'Order updated successfully', 'data': serializer.data}
                if billing:
                    response_data['billing_id'] = billing.id
                    response_data['billing'] = BillingSerializer(billing).data

                return Response(response_data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, business_id=None, order_id=None):
        try:
            if not business_id or not order_id:
                return Response({"error": "Business ID and Order ID are required in the url"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                order_obj = Order.objects.get(
                    id=order_id, business_id=business_id)
            except Order.DoesNotExist:
                return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

            order_obj.delete()
            return Response({'message': 'Order deleted successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CounterView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id=None, counter_id=None):
        try:
            if not business_id:
                return Response({"error": "Business ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)

            if counter_id:
                counter = Counter.objects.select_related('business_id').filter(
                    id=counter_id, business_id=business_id).first()
                if not counter:
                    return Response({"error": "Counter not found"}, status=status.HTTP_404_NOT_FOUND)
                serializer = CounterSerializer(counter)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                counters = Counter.objects.filter(
                    business_id=business_id).select_related('business_id')
                serializer = CounterSerializer(counters, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, business_id=None):
        try:
            data = request.data
            data['business_id'] = business_id

            if not business_id:
                return Response({"error": "Business ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)

            required_fields = ['counter_number', 'business_id']
            for field in required_fields:
                if field not in data:
                    return Response({"error": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST)
            serializer = CounterSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Counter created successfully", "data": serializer.data}, status=status.HTTP_201_CREATED)
            else:
                return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OrderStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        statuses = OrderStatus.objects.all()
        data = [{"id": s.id, "name": s.name} for s in statuses]
        return Response(data, status=status.HTTP_200_OK)


class AssociationRulesView(APIView):
    """
    GET /api/inventory/rules/
    Returns all saved Apriori rules for the business.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id=None):
        if not business_id:
            return Response(
                {"error": "Business ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        business = Business.objects.filter(id=business_id).first()
        if not business:
            return Response(
                {"error": "No business found for this user"},
                status=status.HTTP_404_NOT_FOUND
            )

        rules = AprioriRule.objects.filter(
            business_id=business
        ).order_by('-confidence')

        if not rules.exists():
            return Response(
                {
                    "message": "No rules found. Trigger a retrain first.",
                    "rules": []
                },
                status=status.HTTP_200_OK
            )

        serializer = AprioriRuleSerializer(rules, many=True)
        return Response({
            "total_rules": rules.count(),
            "business": business.business_name,
            "rules": serializer.data
        })


class ReorderSuggestionsView(APIView):
    """
    GET /api/inventory/suggestions/
    Returns reorder suggestions based on low stock items
    and Apriori association rules.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id=None):
        if not business_id:
            return Response(
                {"error": "Business ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        business = Business.objects.filter(id=business_id).first()
        if not business:
            return Response(
                {"error": "No business found for this user"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get low stock products using dynamic check
        from django.db.models import F
        low_stock = Product.objects.filter(
            business_id=business,
            quantity__lte=F('reorder_level')
        )

        # Get suggestions from Apriori (now handles missing rules gracefully)
        result = get_reorder_suggestions(business_id=business.id)

        if 'error' in result:
            return Response(
                {"error": result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enrich suggestions with current stock info
        enriched = []
        for suggestion in result['suggestions']:
            product = Product.objects.filter(
                business_id=business,
                product_name=suggestion['low_stock_product']
            ).first()

            enriched.append({
                "low_stock_product": suggestion['low_stock_product'],
                "current_quantity": product.quantity if product else 0,
                "reorder_level": product.reorder_level if product else 0,
                "also_reorder": suggestion['also_reorder']
            })

        return Response({
            "business": business.business_name,
            "low_stock_count": low_stock.count(),
            "suggestions": enriched
        })


class StockAlertsView(APIView):
    """
    GET /api/inventory/alerts/
    Returns all unresolved stock alerts for the business.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id=None):
        if not business_id:
            return Response(
                {"error": "Business ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        business = Business.objects.filter(id=business_id).first()
        if not business:
            return Response(
                {"error": "No business found for this user"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Optional filter: ?resolved=true to see resolved alerts
        show_resolved = request.query_params.get('resolved', 'false')
        is_resolved = show_resolved.lower() == 'true'

        alerts = StockAlert.objects.filter(
            business_id=business,
            is_resolved=is_resolved
        ).select_related('product').order_by('-created_at')

        serializer = StockAlertSerializer(alerts, many=True)

        return Response({
            "business": business.business_name,
            "total_alerts": alerts.count(),
            "showing": "resolved" if is_resolved else "unresolved",
            "alerts": serializer.data
        })


class ResolveAlertView(APIView):
    """
    PUT /api/inventory/alerts/<id>/resolve/
    Marks a specific stock alert as resolved.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, alert_id, business_id=None):
        if not business_id:
            return Response(
                {"error": "Business ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        business = Business.objects.filter(id=business_id).first()
        if not business:
            return Response(
                {"error": "No business found for this user"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            alert = StockAlert.objects.get(
                id=alert_id,
                business_id=business
            )
        except StockAlert.DoesNotExist:
            return Response(
                {"error": f"Alert #{alert_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        alert.is_resolved = True
        alert.save()

        return Response({
            "message": f"Alert #{alert_id} resolved successfully",
            "alert_id": alert_id,
            "product": alert.product.product_name,
            "is_resolved": True
        })


class RetrainAprioriView(APIView):
    """
    POST /api/inventory/retrain/
    Manually triggers an Apriori retrain for the business.
    Useful for the owner to retrain on demand.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, business_id=None):
        if not business_id:
            return Response(
                {"error": "Business ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        business = Business.objects.filter(id=business_id).first()
        if not business:
            return Response(
                {"error": "No business found for this user"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Run retrain
        rules, message = run_apriori(business_id=business.id)

        if rules is None:
            return Response(
                {"error": message},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save new rules
        save_result = save_rules_to_db(
            business_id=business.id,
            rules=rules
        )

        # Create alerts
        alert_result = create_apriori_stock_alerts(
            business_id=business.id
        )

        return Response({
            "message": "Retrain completed successfully",
            "business": business.business_name,
            "rules_found": message,
            "rules_saved": save_result['saved_new_rules'],
            "old_rules_deleted": save_result['deleted_old_rules'],
            "alerts_created": alert_result.get('total_created', 0),
            "alerts_skipped": alert_result.get('total_skipped', 0)
        })


class ManualAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, shift_id):
        try:
            employee_id = request.data.get("employee_id")
            shift = Shift.objects.get(id=shift_id)
            employee = Employee.objects.get(id=employee_id)

            shift.assigned_employee = employee
            shift.is_scheduled = True
            shift.save()

            EmployeeSchedule.objects.get_or_create(
                employee=employee,
                date=shift.shift_date,
                start_time=shift.start_time,
                end_time=shift.end_time,
            )
            return Response({
                "message":  f"{employee.name} manually assigned.",
                "shift_id": shift.id,
                "assigned": employee.name,
            }, status=status.HTTP_200_OK)

        except Shift.DoesNotExist:
            return Response({"error": "Shift not found"}, status=404)
        except Employee.DoesNotExist:
            return Response({"error": "Employee not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class SkillView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id):
        try:
            skills = Skill.objects.filter(business_id=business_id)
            serializer = SkillSerializer(skills, many=True)
            return Response({'status': 'success', 'data': serializer.data})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)

    def post(self, request, business_id):
        try:
            data = request.data.copy()
            data['business_id'] = business_id
            serializer = SkillSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({'status': 'success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)

    def put(self, request, business_id, skill_id):
        try:
            skill = Skill.objects.get(id=skill_id, business_id=business_id)
        except Skill.DoesNotExist:
            return Response({'error': 'Skill not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SkillSerializer(skill, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'success', 'data': serializer.data})
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, business_id, skill_id):
        try:
            skill = Skill.objects.get(id=skill_id, business_id=business_id)
            skill.delete()
            return Response({'status': 'success', 'message': 'Skill deleted'})
        except Skill.DoesNotExist:
            return Response({'error': 'Skill not found'}, status=status.HTTP_404_NOT_FOUND)


class EmployeeSkillView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id, employee_id):
        try:
            employee_skills = EmployeeSkill.objects.filter(
                employee__business_id=business_id, employee_id=employee_id
            ).select_related('employee', 'skill')
            serializer = EmployeeSkillSerializer(employee_skills, many=True)
            return Response({'status': 'success', 'data': serializer.data})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)

    def post(self, request, business_id, employee_id):
        data = request.data.copy()
        data['employee'] = employee_id

        skill_id = data.get('skill')
        try:
            employee_skill = EmployeeSkill.objects.get(
                employee_id=employee_id, skill_id=skill_id)
            serializer = EmployeeSkillSerializer(
                employee_skill, data=data, partial=True)
            status_code = status.HTTP_200_OK
        except EmployeeSkill.DoesNotExist:
            serializer = EmployeeSkillSerializer(data=data)
            status_code = status.HTTP_201_CREATED

        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'success', 'data': serializer.data}, status=status_code)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, business_id, employee_id, skill_id):
        try:
            employee_skill = EmployeeSkill.objects.get(
                employee_id=employee_id, skill_id=skill_id, employee__business_id=business_id)
            employee_skill.delete()
            return Response({'status': 'success', 'message': 'Skill removed from employee'})
        except EmployeeSkill.DoesNotExist:
            return Response({'error': 'Employee skill not found'}, status=status.HTTP_404_NOT_FOUND)


class ShiftCRUDView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id):
        shifts = Shift.objects.filter(business_id=business_id).select_related(
            'business_id', 'assigned_employee', 'required_skill'
        ).order_by('-shift_date', '-start_time')
        serializer = ShiftSerializer(shifts, many=True)
        return Response({'status': 'success', 'data': serializer.data})

    def post(self, request, business_id):
        data = request.data.copy()
        data['business_id'] = business_id
        serializer = ShiftSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, business_id, shift_id):
        try:
            shift = Shift.objects.get(id=shift_id, business_id=business_id)
        except Shift.DoesNotExist:
            return Response({'error': 'Shift not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ShiftSerializer(shift, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'success', 'data': serializer.data})
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, business_id, shift_id):
        try:
            shift = Shift.objects.get(id=shift_id, business_id=business_id)
            shift.delete()
            return Response({'status': 'success', 'message': 'Shift deleted'})
        except Shift.DoesNotExist:
            return Response({'error': 'Shift not found'}, status=status.HTTP_404_NOT_FOUND)


class ReminderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id, reminder_id=None):
        try:
            if reminder_id:
                try:
                    reminder = Reminder.objects.get(
                        id=reminder_id, business=business_id)
                    serializer = ReminderSerializer(reminder)
                    return Response({'status': 'success', 'data': serializer.data})
                except Reminder.DoesNotExist:
                    return Response({'error': 'Reminder not found'}, status=status.HTTP_404_NOT_FOUND)
            reminders = Reminder.objects.filter(
                business=business_id).order_by('due_date')
            serializer = ReminderSerializer(reminders, many=True)
            return Response({'status': 'success', 'data': serializer.data})
        except Exception:
            return Response({'status': 'success', 'data': []})

    def post(self, request, business_id):
        data = request.data.copy()
        data['business'] = business_id
        serializer = ReminderSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'status': 'error', 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, business_id, reminder_id):
        try:
            reminder = Reminder.objects.get(
                id=reminder_id, business=business_id)
        except Reminder.DoesNotExist:
            return Response({'error': 'Reminder not found'}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data['business'] = business_id
        serializer = ReminderSerializer(reminder, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'success', 'data': serializer.data})
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, business_id, reminder_id):
        try:
            reminder = Reminder.objects.get(
                id=reminder_id, business=business_id)
            reminder.delete()
            return Response({'status': 'success', 'message': 'Reminder deleted'})
        except Reminder.DoesNotExist:
            return Response({'error': 'Reminder not found'}, status=status.HTTP_404_NOT_FOUND)
