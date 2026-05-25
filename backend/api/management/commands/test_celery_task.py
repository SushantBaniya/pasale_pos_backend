# yourapp/management/commands/test_celery_task.py

from django.core.management.base import BaseCommand
from api.models import Business, AprioriRule
from api.tasks import retrain_apriori_for_business
from api.utils.apiriori_utils import load_rules_from_db


class Command(BaseCommand):
    help = 'Tests the retrain task manually'

    def handle(self, *args, **kwargs):

        try:
            business = Business.objects.get(
                business_name='Sharma General Store'
            )
        except Business.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                '❌ Run seed_apriori_data first'
            ))
            return

        self.stdout.write('\n' + '='*60)
        self.stdout.write('     RETRAIN TASK TEST')
        self.stdout.write('='*60)

        # Run task directly
        self.stdout.write('\n🔄 Running retrain task...')
        result = retrain_apriori_for_business(business_id=business.id)

        self.stdout.write('\n📊 Task Result:')
        for key, value in result.items():
            self.stdout.write(f'   {key}: {value}')

        # Show saved rules
        self.stdout.write('\n📋 Rules saved in database:')
        saved_rules = AprioriRule.objects.filter(
            business_id=business
        ).order_by('-confidence')

        for rule in saved_rules:
            self.stdout.write(
                f'   {rule.antecedent} → {rule.consequent} | '
                f'Confidence: {rule.confidence:.0%} | '
                f'Lift: {rule.lift}'
            )

        self.stdout.write('\n📡 Loading via load_rules_from_db():')
        loaded = load_rules_from_db(business_id=business.id)
        self.stdout.write(f'   Total rules loaded: {len(loaded)}')
        if loaded:
            self.stdout.write(f'   Sample: {loaded[0]}')

        self.stdout.write('\n' + '='*60)
        self.stdout.write('     TASK TEST COMPLETE ✅')
        self.stdout.write('='*60 + '\n')