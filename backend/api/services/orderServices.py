from django.db import transaction, models
from django.db.models import Prefetch
from rest_framework import status
from rest_framework.response import Response

from api.models import (
    Business,
    Counter,
    Customer,
    Order,
    OrderItem,
    OrderItemStatus,
    OrderStatus,
    Product,
    StockAlert,
)
from api.serializers import OrderSerializer
from orderCart.models import OrderCart


def get_order(business_id, order_id=None, counter_id=None, customer_id=None, status_name=None):
    try:
        if not business_id:
            raise ValueError("Business ID is required to fetch orders.")

        from django.db.models import Prefetch
        # Base queryset filtered by business with optimized fetching
        orders = Order.objects.filter(business_id=business_id).select_related(
            'order_status', 'customer_id', 'business_id', 'counter'
        ).prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related(
                'status', 'product_id'))
        )

        if order_id:
            orders = orders.filter(id=order_id)
        if counter_id:
            orders = orders.filter(counter_id=counter_id)
        if customer_id:
            orders = orders.filter(customer_id=customer_id)
        if status_name:
            orders = orders.filter(order_status__name__iexact=status_name)

        # Order by creation date (newest first)
        orders = orders.order_by('-created_at')

        serializer = OrderSerializer(orders, many=True)
        return serializer.data

    except Exception as e:
        raise Exception(f"Error fetching order(s): {str(e)}")


def create_order(data, business_id, counter_id=None, customer_id=None):
    try:
        if not isinstance(data, dict):
            return Response(
                {'error': 'Invalid payload format. Expected a JSON object.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = dict(data)

        if business_id is not None:
            data['business_id'] = business_id
        if customer_id is not None:
            data['customer_id'] = customer_id
        if counter_id is not None:
            data['counter_id'] = counter_id

        required_fields = ['business_id', 'total_amount']
        missing_fields = [
            f for f in required_fields if data.get(f) in (None, '')]
        if missing_fields:
            return Response(
                {'error': f'Missing required fields: {missing_fields}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        numeric_fields = ['tax', 'discount', 'total_amount']
        for field in numeric_fields:
            try:
                data[field] = float(data.get(field, 0))
            except (ValueError, TypeError):
                return Response(
                    {'error': f'Invalid value for {field}. Must be a number.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        business_id = data['business_id']
        customer_id = data.get('customer_id')
        counter_id = data.get('counter_id')

        has_customer = customer_id not in (None, '')
        has_counter = counter_id not in (None, '')
        if has_customer == has_counter:
            return Response(
                {'error': 'Provide exactly one of customer_id or counter_id.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not Business.objects.filter(id=business_id).exists():
            return Response({'error': 'Business does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        if counter_id and not Counter.objects.filter(id=counter_id, business_id=business_id).exists():
            return Response(
                {'error': 'Counter does not exist for this business.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if has_customer and not Customer.objects.filter(id=customer_id, business_id=business_id).exists():
            return Response(
                {'error': 'Customer does not exist for this business.'},
                status=status.HTTP_404_NOT_FOUND
            )

        items_data = data.pop('items', []) or []

        # If nested items are not sent, fallback to existing cart items.
        cart_items = []
        if not items_data:
            if not has_customer:
                return Response(
                    {'error': 'items are required when creating a counter order without customer_id.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            cart_items = list(
                OrderCart.objects.filter(
                    business_id=business_id, customer=customer_id)
                .select_related('product')
            )
            if not cart_items:
                return Response(
                    {'error': 'No order items provided and cart is empty.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        product_ids = list({
            item.get('product_id') for item in items_data if item.get('product_id')
        })
        product_map = {
            p.id: p for p in Product.objects.filter(id__in=product_ids)
        } if product_ids else {}

        status_ids = list({
            item.get('status_id') for item in items_data if item.get('status_id')
        })
        item_status_map = {
            s.id: s for s in OrderItemStatus.objects.filter(id__in=status_ids)
        } if status_ids else {}

        pending_item_status = OrderItemStatus.objects.filter(
            name__iexact='Pending').first()

        order_item_objects = []
        qty_by_product_id = {}
        if items_data:
            for idx, item in enumerate(items_data):
                item_missing = [
                    f for f in ['product_id', 'quantity']
                    if item.get(f) in (None, '')
                ]
                if item_missing:
                    return Response(
                        {'error': f'Item #{idx + 1} missing fields: {item_missing}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                product_obj = product_map.get(item['product_id'])
                if not product_obj:
                    return Response(
                        {'error': 'Product not found.',
                            'item_id': item['product_id']},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                try:
                    quantity = int(item['quantity'])
                    if quantity <= 0:
                        raise ValueError()
                except (TypeError, ValueError):
                    return Response(
                        {'error': f'Invalid quantity for item #{idx + 1}. Must be a positive integer.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                item_status_id = item.get('status_id')
                if item_status_id and item_status_id not in item_status_map:
                    return Response(
                        {'error': f'Invalid status_id for item #{idx + 1}.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                unit_price = float(product_obj.unit_price)
                order_item_objects.append(
                    OrderItem(
                        product_id=product_obj,
                        quantity=quantity,
                        unit_price=unit_price,
                        total_price=unit_price * quantity,
                        status=item_status_map.get(
                            item_status_id) or pending_item_status,
                    )
                )
                qty_by_product_id[product_obj.id] = (
                    qty_by_product_id.get(product_obj.id, 0) + quantity
                )
        else:
            for cart_item in cart_items:
                unit_price = float(cart_item.unit_price)
                quantity = int(cart_item.quantity)
                order_item_objects.append(
                    OrderItem(
                        product_id=cart_item.product,
                        quantity=quantity,
                        unit_price=unit_price,
                        total_price=unit_price * quantity,
                        status=pending_item_status,
                    )
                )
                qty_by_product_id[cart_item.product_id] = (
                    qty_by_product_id.get(cart_item.product_id, 0) + quantity
                )

        # Pre-fetch status outside transaction
        pending_order_status = OrderStatus.objects.filter(
            name__iexact='Pending').first()
        if not pending_order_status:
            pending_order_status = OrderStatus.objects.create(name='Pending')

        with transaction.atomic():
            order_obj = Order.objects.create(
                customer_id_id=customer_id,
                business_id_id=business_id,
                counter_id=counter_id,
                order_status=pending_order_status,
                tax=data.get('tax', 0),
                discount=data.get('discount', 0),
                total_amount=data['total_amount'],
            )

            for obj in order_item_objects:
                obj.order = order_obj

            created_items = OrderItem.objects.bulk_create(
                order_item_objects) if order_item_objects else []

            # Update product stock levels in bulk and handle alerts once per product.
            if qty_by_product_id:
                locked_products = list(
                    Product.objects.select_for_update()
                    .filter(id__in=list(qty_by_product_id.keys()))
                )
                low_stock_ids = []
                resolved_ids = []
                for product in locked_products:
                    sold_qty = qty_by_product_id.get(product.id, 0)
                    if sold_qty:
                        product.quantity = max(0, product.quantity - sold_qty)
                        reorder_level = (
                            product.reorder_level
                            if product.reorder_level is not None
                            else 10
                        )
                        product.is_low_stock = product.quantity <= reorder_level
                        if product.is_low_stock:
                            low_stock_ids.append(product.id)
                        else:
                            resolved_ids.append(product.id)

                if locked_products:
                    Product.objects.bulk_update(
                        locked_products, ['quantity', 'is_low_stock']
                    )

                if low_stock_ids:
                    existing_alerts = set(
                        StockAlert.objects.filter(
                            product_id__in=low_stock_ids,
                            is_resolved=False,
                        ).values_list('product_id', flat=True)
                    )
                    new_alerts = []
                    for product in locked_products:
                        if (
                            product.id in low_stock_ids
                            and product.id not in existing_alerts
                            and product.business_id_id
                        ):
                            new_alerts.append(
                                StockAlert(
                                    product_id=product.id,
                                    business_id=product.business_id_id,
                                    is_resolved=False,
                                    message=(
                                        f"Low Stock Alert: {product.product_name} "
                                        f"only has {product.quantity} left!"
                                    ),
                                )
                            )
                    if new_alerts:
                        StockAlert.objects.bulk_create(
                            new_alerts, ignore_conflicts=True
                        )

                if resolved_ids:
                    StockAlert.objects.filter(
                        product_id__in=resolved_ids,
                        is_resolved=False,
                    ).update(is_resolved=True)

            if has_customer:
                OrderCart.objects.filter(
                    business_id=business_id, customer=str(customer_id)).delete()

        # Refresh from DB with pre-fetches for the serializer to avoid N+1
        order_obj = Order.objects.select_related(
            'order_status', 'customer_id', 'business_id', 'counter'
        ).prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related(
                'status', 'product_id'))
        ).get(id=order_obj.id)

        response_data = OrderSerializer(order_obj).data

        return Response({
            'message': 'Order created successfully.',
            'order': response_data,
            'counter_id': order_obj.counter_id,
            'items_created': len(created_items),
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {'error': f'C0INSERR: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
