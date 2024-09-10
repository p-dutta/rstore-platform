from decouple import config
from saleor.celeryconf import app
from celery.schedules import crontab
import datetime
from .models import Rule
from ..account.views.bi import get_bi_data
from ..account.views.user import get_user_data


@app.task
def deactivate_expired_rules():
    active_rules = Rule.objects.filter(is_active=True)
    expired_active_rules = []
    for rule in active_rules:
        timeline = rule.get_latest_rule().client_rule.get('timeline')
        use_timeline = timeline.get('use_timeline')
        if use_timeline:
            end_date = timeline.get('end_date')
            formatted_end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            if formatted_end_date < datetime.datetime.now():
                rule.is_active = False
                expired_active_rules.append(rule)

    Rule.objects.bulk_update(expired_active_rules, fields=['is_active'])


e_hour, e_minute = [int(z) for z in (config("DEACTIVATE_RULE").split(','))]
b_hour, b_minute = [int(z) for z in (config("BI_RECEIPT_GENERATION").split(','))]


@app.task
def export_bi_report_data():
    get_bi_data(bi=True)


@app.task
def export_bi_user_report_data():
    get_user_data(bi=True)


app.conf.timezone = "Asia/Dhaka"
app.conf.beat_schedule = {
    'deactivate_expired_rules': {
        'task': 'saleor.commission.tasks.deactivate_expired_rules',
        'schedule': crontab(hour=e_hour, minute=e_minute)
    },
    'export_bi_report': {
        'task': 'saleor.commission.tasks.export_bi_report_data',
        'schedule': crontab(hour=b_hour, minute=b_minute)
    },
    'export_bi_user_report': {
        'task': 'saleor.commission.tasks.export_bi_user_report_data',
        'schedule': crontab(hour=b_hour, minute=b_minute)
    }
}
