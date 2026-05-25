from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0020_orderitemstatus_orderstatus_billing_business_id_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS api_usersettings;",
            reverse_sql="",
        ),
    ]