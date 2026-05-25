from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_otp_email(email, otp):
    try:
        subject = 'Your OTP Code'
        message = f'Your OTP code is: {otp}'
        email_from = settings.EMAIL_HOST_USER
        recipient_list = [email]

        send_mail(subject, message, email_from,
                  recipient_list, fail_silently=False)
        logger.info(f"OTP email sent successfully to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {str(e)}")
        return False
    


from api.models import Business
from api.utils.apiriori_utils import (
    run_apriori,
    save_rules_to_db,
    create_apriori_stock_alerts
)
import logging

logger = logging.getLogger(__name__)

def retrain_apriori_for_all_businesses():
    """
    Retrains Apriori for every business.
    Scheduled via Django-Q.
    """
    businesses = Business.objects.all()
    summary = []

    for business in businesses:
        try:
            logger.info(f"Retraining: {business.business_name}")

            rules, message = run_apriori(business_id=business.id)

            if rules is None:
                summary.append({
                    "business": business.business_name,
                    "status": "skipped",
                    "reason": message
                })
                continue

            save_result = save_rules_to_db(
                business_id=business.id,
                rules=rules
            )
            alert_result = create_apriori_stock_alerts(
                business_id=business.id
            )

            summary.append({
                "business": business.business_name,
                "status": "success",
                "rules_saved": save_result['saved_new_rules'],
                "alerts_created": alert_result.get('total_created', 0)
            })

        except Exception as e:
            logger.error(f"Failed for {business.business_name}: {str(e)}")
            summary.append({
                "business": business.business_name,
                "status": "failed",
                "error": str(e)
            })

    return summary


def retrain_apriori_for_business(business_id):
    """
    Retrains Apriori for a single business.
    """
    try:
        business = Business.objects.get(id=business_id)
        rules, message = run_apriori(business_id=business_id)

        if rules is None:
            return {"status": "skipped", "reason": message}

        save_result = save_rules_to_db(
            business_id=business_id,
            rules=rules
        )
        alert_result = create_apriori_stock_alerts(
            business_id=business_id
        )

        return {
            "status": "success",
            "business": business.business_name,
            "rules_saved": save_result['saved_new_rules'],
            "alerts_created": alert_result.get('total_created', 0)
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}