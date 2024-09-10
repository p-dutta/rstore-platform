from business_rules import run_all

from .commission_calculation import OrderVariables, OrderActions
from .models import Commission, RuleHistory, Rule
from ..celeryconf import app

from ..order.models import Order

from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@app.task
def recalculate_commission_on_rule_update(rule_id, if_timeline, start_date, end_date):

    rule_instance = Rule.objects.get(pk=rule_id)
    rule_history_ids = rule_instance.get_rule_histories_pk_list()
    latest_rule_history = rule_instance.get_latest_rule()

    if len(rule_history_ids) > 0:
        commissions = Commission.objects.filter(
            rule_history__pk__in=rule_history_ids,
            commission_service_month__status="pending"
        )

        if if_timeline:
            commissions = commissions.filter(
                order__created__date__gte=start_date,
                order__created__date__lte=end_date
            )

        orders = Order.objects.filter(commissions__in=commissions)

        if if_timeline:
            orders = orders.filter(
                created__date__gte=start_date,
                created__date__lte=end_date
            )

        order_ids = orders.values_list('pk', flat=True)

        order_ids = list(order_ids)

        # for order in orders:
        #     logger.info(order.__dict__)

        if len(order_ids) > 0:
            commissions.delete()

        orders = Order.objects.filter(pk__in=order_ids)

        for order in orders:
            run_all(
                rule_list=latest_rule_history.engine_rule,
                defined_variables=OrderVariables(order),
                defined_actions=OrderActions(order),
                stop_on_first_trigger=False
            )


@app.task
def recalculate_commission_on_rule_delete(rule_history_ids):
    commissions = Commission.objects.filter(
        rule_history__pk__in=rule_history_ids,
        commission_service_month__status="pending"
    )

    commissions.delete()
