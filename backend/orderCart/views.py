from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .serializers import OrderCartSerializer
from api.models import Customer, Product
from .models import OrderCart


class OrderCartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id=None, customer_id=None):
        try:
            if not business_id:
                return Response({"error": "Business ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)
            if not customer_id:
                return Response({"error": "Customer ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the customer exists
            if not Customer.objects.filter(id=customer_id).exists():
                return Response({"error": "Customer does not exist"}, status=status.HTTP_404_NOT_FOUND)

            order_carts = OrderCart.objects.filter(
                business_id=business_id, customer_id=customer_id)
            serializer = OrderCartSerializer(order_carts, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, business_id=None, customer_id=None):
        try:
            data = request.data
            if not business_id:
                return Response({"error": "Business ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)
            customer_value = None
            if customer_id:
                if not Customer.objects.filter(id=customer_id).exists():
                    return Response({"error": "Customer does not exist"}, status=status.HTTP_404_NOT_FOUND)
                customer_value = str(customer_id)

            if isinstance(data, dict):
                items_data = data.get('items', [])
                customer_value = customer_value or data.get(
                    'customer') or data.get('counter')
            else:
                items_data = data
                customer_value = customer_value or request.query_params.get(
                    'customer') or request.query_params.get('counter')

            if not customer_value:
                return Response({"error": "Customer or counter is required."}, status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(items_data, list):
                return Response({"error": "Invalid data format. Expected a list of items."}, status=status.HTTP_400_BAD_REQUEST)

            product_ids = []
            for item in items_data:
                if 'unit_price' not in item or 'quantity' not in item:
                    return Response({"error": "unit_price and quantity are required for each item."}, status=status.HTTP_400_BAD_REQUEST)

                product_id = item.get('product_id') or item.get('Product_id')
                if not product_id:
                    return Response({"error": "product_id is required for each item."}, status=status.HTTP_400_BAD_REQUEST)
                product_ids.append(product_id)

            product_map = Product.objects.in_bulk(product_ids)
            missing_ids = [
                pid for pid in product_ids if pid not in product_map]
            if missing_ids:
                return Response(
                    {"error": f"Product with ID {missing_ids[0]} does not exist."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            cart_objects = []
            for item in items_data:
                try:
                    unit_price = float(item['unit_price'])
                    quantity = int(item['quantity'])
                except (TypeError, ValueError):
                    return Response(
                        {"error": "unit_price and quantity must be valid numbers."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                product_id = item.get('product_id') or item.get('Product_id')

                cart_objects.append(
                    OrderCart(
                        business_id_id=business_id,
                        customer=str(customer_value),
                        product_id=product_id,
                        unit_price=unit_price,
                        quantity=quantity,
                        total_amount=unit_price * quantity,
                    )
                )

            created_items = OrderCart.objects.bulk_create(cart_objects)
            serializer = OrderCartSerializer(created_items, many=True)
            return Response(
                {"message": "Items added to cart successfully",
                    "data": serializer.data},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, business_id=None, customer_id=None, cart_id=None):
        try:
            if not business_id:
                return Response({"error": "Business ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)
            if not customer_id:
                return Response({"error": "Customer ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)
            if not cart_id:
                return Response({"error": "Cart ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the customer exists
            if not Customer.objects.filter(id=customer_id).exists():
                return Response({"error": "Customer does not exist"}, status=status.HTTP_404_NOT_FOUND)

            order_cart = OrderCart.objects.filter(
                id=cart_id, business_id=business_id, customer_id=customer_id).first()
            if not order_cart:
                return Response({"error": "Order cart item not found"}, status=status.HTTP_404_NOT_FOUND)

            serializer = OrderCartSerializer(
                order_cart, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Order cart item updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, business_id=None, customer_id=None, cart_id=None):
        try:
            if not business_id:
                return Response({"error": "Business ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)
            if not customer_id:
                return Response({"error": "Customer ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)
            if not cart_id:
                return Response({"error": "Cart ID is required in the url"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the customer exists
            if not Customer.objects.filter(id=customer_id).exists():
                return Response({"error": "Customer does not exist"}, status=status.HTTP_404_NOT_FOUND)

            order_cart = OrderCart.objects.filter(
                id=cart_id, business_id=business_id, customer_id=customer_id).first()
            if not order_cart:
                return Response({"error": "Order cart item not found"}, status=status.HTTP_404_NOT_FOUND)

            order_cart.delete()

            remaining_items = OrderCart.objects.filter(
                business_id=business_id, customer_id=customer_id).exists()
            if not remaining_items:
                try:
                    customer_obj = Customer.objects.get(id=customer_id)
                    customer_obj.delete()
                except Exception as e:
                    return Response({"error": f"Failed to delete customer: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
