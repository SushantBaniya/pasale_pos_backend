from api.models import Product, Business, StockAlert
from api.serializers import ProductSerializer
from rest_framework.response import Response


def check_low_stock_and_alert(product_id):
    try:
        product = Product.objects.get(id=product_id)

        if product.quantity <= product.reorder_level:
            if not product.is_low_stock:
                # Update product status
                product.is_low_stock = True
                product.save(update_fields=['is_low_stock'])

                # Create the unread alert notification
                StockAlert.objects.get_or_create(
                    product=product,
                    business_id=product.business_id,
                    is_resolved=False,
                    defaults={
                        'message': f"Low Stock Alert: {product.product_name} only has {product.quantity} left!"}
                )
        else:
            # If stock is now above threshold, resolve automatically
            if product.is_low_stock:
                product.is_low_stock = False
                product.save(update_fields=['is_low_stock'])
                StockAlert.objects.filter(
                    product=product, is_resolved=False).update(is_resolved=True)

    except Product.DoesNotExist:
        return Response({'message': 'Product not found.'})


def get_product(product_id=None, business_id=None):
    try:
        if product_id:
            products = Product.objects.filter(
                id=product_id, business_id=business_id
            ).select_related('category', 'business_id')
            serializer = ProductSerializer(products, many=True)
            return serializer.data

        if business_id:
            products = Product.objects.filter(
                business_id=business_id
            ).select_related('category', 'business_id')
            serializer = ProductSerializer(products, many=True)
            return serializer.data

    except Exception as e:
        raise Exception(f"Error fetching product(s): {str(e)}")


def create_product(data):
    try:
        data = dict(data)

        # Auto-handle category string names
        if 'category' in data and isinstance(data['category'], str) and not data['category'].isdigit():
            from api.models import Category
            cat, _ = Category.objects.get_or_create(name=data['category'])
            data['category'] = cat.id

        required_fields = ['product_name', 'category',
                           'unit_price', 'quantity', 'business_id']
        for field in required_fields:
            if field not in data:
                raise Exception(f"{field} is required.")

        if not Business.objects.filter(id=data['business_id']).exists():
            raise Exception(
                "Business does not exist.")

        serializer = ProductSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return {'message': 'Product created successfully!', 'product': serializer.data}
        else:
            raise Exception(f"Validation Error: {serializer.errors}")

    except Exception as e:
        raise Exception(f"Error creating product: {str(e)}")
