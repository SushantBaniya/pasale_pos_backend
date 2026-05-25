

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import (
    Business, Product, Category, Order,
    OrderItem, OrderStatus
)
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Seeds fake POS transaction data for Apriori testing'

    def handle(self, *args, **kwargs):

        self.stdout.write('🔄 Step 1: Setting up user and business...')

        # --- User & Business ---
        user, _ = User.objects.get_or_create(username='testowner')
        user.set_password('test1234')
        user.save()

        business, _ = Business.objects.get_or_create(
            user=user,
            defaults={'business_name': 'Sharma General Store'}
        )
        self.stdout.write(f'   ✅ Business: {business.business_name} (id={business.id})')

        # --- Category ---
        self.stdout.write('🔄 Step 2: Creating category...')
        cat, _ = Category.objects.get_or_create(
            name='Grocery',
            defaults={'slug': 'grocery'}
        )
        self.stdout.write(f'   ✅ Category: {cat.name}')

        # --- Order Status ---
        self.stdout.write('🔄 Step 3: Creating order status...')
        status, _ = OrderStatus.objects.get_or_create(name='Completed')
        self.stdout.write(f'   ✅ Status: {status.name}')

        # --- Products ---
        self.stdout.write('🔄 Step 4: Creating products...')
        product_data = [
            ('Flour', 50), ('Sugar', 80), ('Butter', 30),
            ('Milk', 100), ('Eggs', 60), ('Bread', 40),
            ('Tea Leaves', 70), ('Dal', 90), ('Rice', 120),
            ('Cooking Oil', 45), ('Yeast', 20), ('Jam', 25),
            ('Instant Noodles', 55), ('Chilli Sauce', 35),
            ('Ghee', 15), ('Spices', 50),
        ]

        products = {}
        for name, qty in product_data:
            p, created = Product.objects.get_or_create(
                product_name=name,
                business_id=business,
                defaults={
                    'user': user,
                    'category': cat,
                    'unit_price': Decimal(str(random.randint(50, 500))),
                    'quantity': qty,
                    'reorder_level': 10,
                }
            )
            products[name] = p
            self.stdout.write(f'   {"✅ Created" if created else "⏭️  Exists"}: {name}')

        # --- Basket Patterns ---
        self.stdout.write('🔄 Step 5: Creating orders with bulk_create...')

        basket_patterns = [
            ['Flour', 'Sugar', 'Yeast'],
            ['Flour', 'Sugar', 'Butter'],
            ['Milk', 'Bread', 'Butter'],
            ['Flour', 'Yeast', 'Milk'],
            ['Bread', 'Butter', 'Jam'],
            ['Flour', 'Sugar', 'Milk', 'Butter'],
            ['Bread', 'Jam', 'Milk'],
            ['Flour', 'Sugar', 'Yeast', 'Butter'],
            ['Milk', 'Butter', 'Bread'],
            ['Flour', 'Sugar', 'Yeast', 'Milk'],
            ['Tea Leaves', 'Milk', 'Sugar'],
            ['Tea Leaves', 'Milk', 'Sugar', 'Bread'],
            ['Tea Leaves', 'Sugar', 'Milk'],
            ['Dal', 'Rice', 'Cooking Oil'],
            ['Dal', 'Rice', 'Ghee', 'Spices'],
            ['Dal', 'Rice', 'Cooking Oil', 'Spices'],
            ['Rice', 'Dal', 'Ghee'],
            ['Eggs', 'Bread', 'Butter'],
            ['Eggs', 'Bread', 'Butter', 'Milk'],
            ['Instant Noodles', 'Eggs', 'Chilli Sauce'],
            ['Instant Noodles', 'Eggs', 'Butter'],
            ['Instant Noodles', 'Chilli Sauce'],
            ['Bread', 'Butter', 'Eggs', 'Jam'],
            ['Milk', 'Sugar', 'Tea Leaves'],
            ['Rice', 'Cooking Oil', 'Spices'],
            ['Flour', 'Butter', 'Sugar', 'Milk'],
            ['Ghee', 'Rice', 'Dal'],
            ['Bread', 'Eggs', 'Milk'],
            ['Yeast', 'Flour', 'Sugar'],
            ['Cooking Oil', 'Dal', 'Rice'],
        ]

        expanded = basket_patterns * 5  # 150 orders
        random.shuffle(expanded)

        # Step A: Bulk create all orders at once
        orders_to_create = [
            Order(
                business_id=business,
                order_status=status,
                total_amount=Decimal('0.00')
            )
            for _ in expanded
        ]
        created_orders = Order.objects.bulk_create(orders_to_create)
        self.stdout.write(f'   ✅ Created {len(created_orders)} orders')

        # Step B: Bulk create all order items at once
        items_to_create = []
        for order, basket in zip(created_orders, expanded):
            total = Decimal('0.00')
            for product_name in basket:
                product = products[product_name]
                qty = random.randint(1, 3)
                price = product.unit_price
                items_to_create.append(
                    OrderItem(
                        order=order,
                        product_id=product,
                        quantity=qty,
                        unit_price=price,
                        total_price=price * qty,
                    )
                )

        OrderItem.objects.bulk_create(items_to_create)
        self.stdout.write(f'   ✅ Created {len(items_to_create)} order items')

        # --- Summary ---
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(
            f'✅ Done! Seeded:\n'
            f'   - Business : {business.business_name}\n'
            f'   - Products : {len(products)}\n'
            f'   - Orders   : {len(created_orders)}\n'
            f'   - Items    : {len(items_to_create)}\n'
        ))
        self.stdout.write('='*50)