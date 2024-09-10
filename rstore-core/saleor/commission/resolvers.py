from dateutil.relativedelta import relativedelta
from django.utils.timezone import make_aware
from datetime import date, timedelta, datetime
from operator import itemgetter
import graphene
from django.db.models import Sum, Count

from .types import CommissionsGroup, Commission as CommissionType, ServiceCommission, MonthlyServiceCommission

from ...account.models import User
from ...commission.models import Rule, Commission, UserProfile, CommissionServiceMonth
from ...partner.models import Partner


def resolve_rules():
    return Rule.objects.all()


def resolve_rule(rule_id):
    _model, rule_pk = graphene.Node.from_global_id(rule_id)
    return Rule.objects.get(id=rule_pk)


def resolve_commissions(info, **kwargs):
    children_list = info.context.user.get_children()
    all_commission = Commission.objects.filter(user_id__in=children_list)

    service_month = {}
    for commission in all_commission:

        commission_service_id = commission.commission_service_month.id
        commission_type: CommissionType = commission

        commission_group: CommissionsGroup = commission.commission_service_month
        commission_group.service_commissions = [commission_type]

        if service_month.__contains__(commission_service_id):
            service_month[commission_service_id].service_commissions.append(commission_type)
        else:
            service_month[commission_service_id] = commission_group

    service_month_list = [csm for csm in service_month.values()]
    return service_month_list


def resolve_commission(commission_service_id):
    _model, commission_service_pk = graphene.Node.from_global_id(commission_service_id)
    csm = CommissionServiceMonth.objects.get(id=commission_service_pk)
    all_commission = list(Commission.objects.filter(commission_service_month=csm).order_by('-order__pk'))

    from .types import CommissionsGroup
    commission_group: CommissionsGroup = csm
    commission_group.service_commissions = all_commission

    return commission_group


def resolve_user_profiles():
    return UserProfile.objects.all()


def resolve_user_profile(user_profile_id):
    _model, user_profile_pk = graphene.Node.from_global_id(user_profile_id)
    return UserProfile.objects.get(id=user_profile_pk)


def resolve_get_user_by_user_profile(info, **kwargs):
    profile_name = kwargs.get('name').lower()
    all_user_profile = UserProfile.objects.all().order_by('priority_order')
    given_profile = all_user_profile.filter(name=profile_name).first()
    all_user_profile = list(all_user_profile)
    users = None
    if given_profile:
        given_profile_index = all_user_profile.index(given_profile)
        next_profile = all_user_profile[given_profile_index + 1] if given_profile_index < len(
            all_user_profile) - 1 else None

        to_date = make_aware(datetime.today().replace(day=1) - timedelta(days=1))
        from_date = to_date + relativedelta(months=-given_profile.period) + timedelta(days=1)

        eligible_user = User.objects.filter(orders__created__range=[from_date, to_date]).distinct()
        if next_profile is None:
            users = eligible_user.annotate(transactions=Sum('orders__total_net_amount'),
                                           total_orders=Count('orders')).filter(
                total_orders__gte=given_profile.total_orders, transactions__gte=given_profile.total_transaction)
        else:
            users = eligible_user.annotate(transactions=Sum('orders__total_net_amount'),
                                           total_orders=Count('orders')).filter(
                total_orders__gte=given_profile.total_orders, transactions__gte=given_profile.total_transaction,
                total_orders__lt=next_profile.total_orders, transactions__gt=next_profile.total_transaction)
    return users


def resolve_monthly_service_commission(info, month):
    date_object = datetime.strptime(month, '%Y-%m')
    year = date_object.year
    month = date_object.month

    # as front-end cliend can not send dynamic year/month now
    currentMonth = datetime.now().month
    currentYear = datetime.now().year
    children_list = info.context.user.get_children()
    commission_entries = Commission.objects.filter(user_id__in=children_list, created__year=currentYear,
                                                   created__month=currentMonth)
    total_commission = commission_entries.aggregate(Sum('amount'))['amount__sum']
    results = commission_entries.values('order__partner_id').order_by('order__partner_id').annotate(
        commission_amount=Sum('amount'))[:3]

    top_services = []
    for result in results:
        service_commission = ServiceCommission(
            commission_amount=result['commission_amount'],
            service=Partner.objects.get(id=result['order__partner_id'])
        )
        top_services.append(service_commission)

    if total_commission is None:
        total_commission = 0

    return MonthlyServiceCommission(total_commission=total_commission, top_services=top_services)
