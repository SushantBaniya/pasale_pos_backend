from django.contrib import admin
from .models import OrderCart

# Register your models here.
@admin.register(OrderCart)
class OrderCartAdmin(admin.ModelAdmin):
    list_display = ('id', 'business_id', 'customer', 'product', 'order_date', 'unit_price', 'quantity', 'total_amount')
    list_filter = ('business_id', 'customer', 'order_date')
    search_fields = ('customer',)