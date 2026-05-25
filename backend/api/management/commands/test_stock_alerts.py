# yourapp/management/commands/test_stock_alerts.py

from django.core.management.base import BaseCommand
from api.models import Business, Product, StockAlert
from api.utils.apiriori_utils import (
    create_apriori_stock_alerts,
    resolve_apriori_alerts
)


class Command(BaseCommand):
    help = 'Tests StockAlert integration with Apriori'

    def handle(self, *args, **kwargs):

        # --- Get test business ---
        try:
            business = Business.objects.get(
                business_name='Sharma General Store'
            )
        except Business.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                '❌ Test business not found. Run seed_apriori_data first.'
            ))
            return

        self.stdout.write('\n' + '='*60)
        self.stdout.write('     STOCK ALERT INTEGRATION TEST')
        self.stdout.write('='*60)

        # --- Step 1: Simulate low stock ---
        self.stdout.write('\n🔴 STEP 1: Simulating low stock products...')
        low_stock_items = ['Dal', 'Flour', 'Bread']

        Product.objects.filter(
            business_id=business,
            product_name__in=low_stock_items
        ).update(is_low_stock=True, quantity=3)

        self.stdout.write(f'   Set low stock: {low_stock_items}')

        # --- Step 2: Run Apriori & create alerts ---
        self.stdout.write('\n🤖 STEP 2: Running Apriori & creating alerts...')
        result = create_apriori_stock_alerts(business_id=business.id)

        if 'error' in result:
            self.stdout.write(self.style.ERROR(f"   ❌ {result['error']}"))
            return

        self.stdout.write(f"   Rules used: {result['rules_used']}")
        self.stdout.write(
            f"   Alerts created : {result['total_created']}"
        )
        self.stdout.write(
            f"   Alerts skipped : {result['total_skipped']} (already exist)"
        )

        # --- Step 3: Show created alerts ---
        self.stdout.write('\n📋 STEP 3: Alerts created in database...')
        for alert in result['alerts_created']:
            self.stdout.write(
                f"\n   ⚠️  Trigger  : {alert['trigger']} is LOW"
            )
            self.stdout.write(
                f"      Reorder  : {alert['reorder']}"
            )
            self.stdout.write(
                f"      Confidence: {alert['confidence']}"
            )
            self.stdout.write(
                f"      Lift      : {alert['lift']}"
            )
            self.stdout.write(
                f"      Alert ID  : #{alert['alert_id']}"
            )

        # --- Step 4: Verify in database ---
        self.stdout.write('\n🗄️  STEP 4: Verifying alerts in database...')
        db_alerts = StockAlert.objects.filter(
            business_id=business,
            is_resolved=False
        )
        self.stdout.write(f'   Total unresolved alerts: {db_alerts.count()}')
        for a in db_alerts:
            self.stdout.write(f'   → [{a.id}] {a.message}')

        # --- Step 5: Simulate restock & resolve alerts ---
        self.stdout.write('\n✅ STEP 5: Simulating restock...')
        Product.objects.filter(
            business_id=business,
            product_name__in=low_stock_items
        ).update(is_low_stock=False, quantity=100)

        resolve_result = resolve_apriori_alerts(business_id=business.id)
        self.stdout.write(
            f"   Alerts resolved: {resolve_result['alerts_resolved']}"
        )

        # --- Final state ---
        remaining = StockAlert.objects.filter(
            business_id=business,
            is_resolved=False
        ).count()
        self.stdout.write(f'   Remaining unresolved alerts: {remaining}')

        self.stdout.write('\n' + '='*60)
        self.stdout.write('     STOCK ALERT TEST COMPLETE ✅')
        self.stdout.write('='*60 + '\n')