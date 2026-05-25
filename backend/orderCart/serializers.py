from .models import OrderCart
from rest_framework import serializers

class OrderCartSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business_id.business_name', read_only=True)
    class Meta:
        model = OrderCart
        fields = ['id', 'business_id', 'customer', 'order_date', 'unit_price', 'quantity', 'total_amount', 'business_name']

        read_only_fields = ['business_name']