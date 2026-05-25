# yourapp/management/commands/test_apriori.py

from django.core.management.base import BaseCommand
from api.models import Business, Product
from api.utils.apiriori_utils import (
    get_transactions,
    run_apriori,
    get_reorder_suggestions
)


class Command(BaseCommand):
    help = 'Tests the Apriori algorithm on seeded data'

    def handle(self, *args, **kwargs):

        # --- Get test business ---
        try:
            business = Business.objects.get(business_name='Sharma General Store')
        except Business.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                '❌ Test business not found. Run seed_apriori_data first.'
            ))
            return

        self.stdout.write('\n' + '='*60)
        self.stdout.write('       APRIORI ALGORITHM TEST')
        self.stdout.write('='*60)

        # --- Test 1: Transaction Extraction ---
        self.stdout.write('\n📦 TEST 1: Transaction Extraction')
        self.stdout.write('-'*40)
        transactions = get_transactions(business_id=business.id)
        self.stdout.write(f'Total transactions loaded: {len(transactions)}')
        self.stdout.write(f'Sample basket 1: {transactions[0]}')
        self.stdout.write(f'Sample basket 2: {transactions[1]}')
        self.stdout.write(f'Sample basket 3: {transactions[2]}')

        # --- Test 2: Rule Generation ---
        self.stdout.write('\n🔍 TEST 2: Association Rule Generation')
        self.stdout.write('-'*40)
        rules, message = run_apriori(
            business_id=business.id,
            min_support=0.2,
            min_confidence=0.5,
            min_lift=1.2
        )
        self.stdout.write(f'Result: {message}')

        if rules is not None and not rules.empty:
            self.stdout.write('\nTop 5 Association Rules:')
            top_rules = rules.head(5)
            for _, rule in top_rules.iterrows():
                ant = list(rule['antecedents'])
                con = list(rule['consequents'])
                self.stdout.write(
                    f'  {ant} → {con} | '
                    f'Confidence: {rule["confidence"]:.0%} | '
                    f'Lift: {rule["lift"]:.2f}'
                )

        # --- Test 3: Low Stock Simulation ---
        self.stdout.write('\n⚠️  TEST 3: Low Stock Simulation')
        self.stdout.write('-'*40)

        # Simulate low stock for flour and tea leaves
        low_stock_products = ['Flour', 'Tea Leaves', 'Dal']
        Product.objects.filter(
            business_id=business,
            product_name__in=low_stock_products
        ).update(is_low_stock=True, quantity=5)

        self.stdout.write(f'Set low stock for: {low_stock_products}')

        # --- Test 4: Reorder Suggestions ---
        self.stdout.write('\n💡 TEST 4: Reorder Suggestions')
        self.stdout.write('-'*40)
        result = get_reorder_suggestions(business_id=business.id)

        if 'error' in result:
            self.stdout.write(self.style.ERROR(f"Error: {result['error']}"))
        else:
            self.stdout.write(f"Status: {result['message']}")
            self.stdout.write(f"Suggestions found: {len(result['suggestions'])}")

            for suggestion in result['suggestions']:
                self.stdout.write(
                    f"\n  ⚠️  '{suggestion['low_stock_product']}' is low stock"
                )
                for item in suggestion['also_reorder']:
                    self.stdout.write(
                        f"     → Also reorder: {item['items']} "
                        f"(Confidence: {item['confidence']} | "
                        f"Lift: {item['lift']})"
                    )

        # --- Reset low stock flags ---
        Product.objects.filter(
            business_id=business,
            product_name__in=low_stock_products
        ).update(is_low_stock=False, quantity=50)

        self.stdout.write('\n✅ Reset low stock flags back to normal')
        self.stdout.write('\n' + '='*60)
        self.stdout.write('       ALL TESTS COMPLETE')
        self.stdout.write('='*60 + '\n')