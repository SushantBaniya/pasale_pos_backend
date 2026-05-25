from django.db import models
from api.models import Product, Business

# Create your models here.

class OrderCart(models.Model):
    business_id = models.ForeignKey(Business, on_delete=models.CASCADE)
    customer = models.CharField(max_length=255)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    order_date = models.DateTimeField(auto_now_add=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"OrderCart {self.id} for {self.customer} - Total: {self.total_amount}"