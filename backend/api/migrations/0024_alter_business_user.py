from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0023_business_is_verified_business_otp_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='business',
            name='user',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name='businesses',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
