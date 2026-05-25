from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0033_fix_missing_reminder'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='party',
            index=models.Index(
                fields=['business_id', 'Category_type'], name='api_party_busines_3f9ea2_idx'),
        ),
        migrations.AddIndex(
            model_name='billing',
            index=models.Index(fields=['business_id', 'invoice_date',
                               'transaction_type'], name='api_billing_busine_4d2c8d_idx'),
        ),
        migrations.AddIndex(
            model_name='reminder',
            index=models.Index(
                fields=['business', 'due_date'], name='api_reminder_busine_1c98d2_idx'),
        ),
    ]
