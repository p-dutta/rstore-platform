import csv
import time
import json
from collections import defaultdict
from datetime import datetime, date, timedelta

import graphene
from dateutil.relativedelta import relativedelta
from django.db.models import Q, Prefetch
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.utils.timezone import make_aware
from django.views import View

from saleor import settings
from saleor.account.models import User, Region, check_profile_matches
from saleor.account.views import get_field_value
from saleor.commission.models import UserProfile
from saleor.decorators import logged_in_required, query_debugger
from saleor.order.models import Order


@method_decorator(logged_in_required, name='get')
class DataExportView(View):
    def get(self, request, *args, **kwargs):
        user = request.user
        start_date = request.GET.get("start_date", None)
        end_date = request.GET.get("end_date", None)
        fields = request.GET.get('fields', None)
        criteria = request.GET.get("criteria", None)
        criteria_value = request.GET.get(criteria, None)
        return get_user_data(user=user, start_date=start_date, end_date=end_date, criteria=criteria,
                             criteria_value=criteria_value, fields=fields)


@query_debugger
def get_user_data(user=None, start_date=None, end_date=None, fields=None, criteria=None, criteria_value=None,
                  bi=False):
    fields = _get_user_fields(fields)

    if bi:
        email = 'rstore_su@rstore.com.bd'
        user = User.objects.get(email=email)
        criteria = 'all'
        criteria_value = '1'

    if criteria:
        if criteria != 'all' and not criteria_value:
            return JsonResponse({"message": "Url criteria parameters incorrect"}, status=400)
        elif criteria == 'cm' or criteria == 'dcm' or criteria == 'dco':
            _, criteria_user_id = graphene.Node.from_global_id(criteria_value)
            criteria_user = User.objects.get(id=criteria_user_id)
            agent_ids = criteria_user.get_children(False)
        elif criteria == 'district':
            _, criteria_district_id = graphene.Node.from_global_id(criteria_value)
            agent_ids = User.objects.filter(regions__district_id=criteria_district_id)
        elif criteria == 'thana':
            _, criteria_thana_id = graphene.Node.from_global_id(criteria_value)
            agent_ids = User.objects.filter(regions__thana_id=criteria_thana_id)
        else:
            agent_ids = user.get_children(False)
    else:
        return HttpResponseBadRequest(json.dumps({"message": "Criteria must be provided"}))

    q = Q(id__in=agent_ids) & Q(groups__name="agent")

    datetime_start_date = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
    datetime_end_time = datetime.strptime(f'{end_date} 23:59:59.999999',
                                          '%Y-%m-%d %H:%M:%S.%f') if end_date else None
    if datetime_start_date:
        q &= Q(created__gte=datetime_start_date)
    if datetime_end_time:
        q &= Q(created__lte=datetime_end_time)

    start_time = time.time()
    queryset_users = User.objects.select_related('default_shipping_address').select_related('default_billing_address') \
        .prefetch_related(
        Prefetch('groups', to_attr='u_groups')
    ).prefetch_related(
        Prefetch(
            'regions', queryset=Region.objects.select_related('district').select_related('thana').all(),
            to_attr='u_regions'
        )
    ).filter(q).order_by('-created')
    print("--- users %s seconds ---" % (time.time() - start_time))

    start_time = time.time()
    orders = Order.objects.select_related('user').all()
    print("--- orders %s seconds ---" % (time.time() - start_time))

    start_time = time.time()
    all_profiles = UserProfile.objects.all().order_by('-priority_order')
    print("--- profiles %s seconds ---" % (time.time() - start_time))

    start_time = time.time()
    managers = User.objects.prefetch_related(
        Prefetch('groups', to_attr='u_groups')
    ).prefetch_related(
        Prefetch('regions', to_attr='u_regions')
    ).filter(groups__name__in=['dco', 'dcm', 'cm'])
    print("--- manager query %s seconds ---" % (time.time() - start_time))

    managers_dict = defaultdict(dict)
    for manager in managers:
        regions = manager.u_regions
        u_group = manager.u_groups[0]
        for region in regions:
            managers_dict[u_group.name][region.pk] = manager
    print("--- manager_dict %s seconds ---" % (time.time() - start_time))

    start_time = time.time()
    for user in queryset_users:
        region = user.u_regions[0].pk
        user.dco = managers_dict['dco'].get(region)
        user.dcm = managers_dict['dcm'].get(region)
        user.cm = managers_dict['cm'].get(region)
    print("--- manager assignment %s seconds ---" % (time.time() - start_time))

    if bi:
        today = date.today()
        file_name = f'user-{today}.csv'
        media_root = settings.MEDIA_ROOT
        bi_file_path = f'{media_root}/bi/{file_name}'

        with open(bi_file_path, 'w', newline='') as file:
            writer = csv.writer(file, delimiter='|')
            header_data = []
            for field in fields:
                replaced_field = field.replace("_", " ").title()
                if replaced_field.startswith('Dco') or replaced_field.startswith('Dcm') or replaced_field.startswith(
                        'Cm'):
                    replaced_field = replaced_field.partition(" ")[0].upper() + " " + replaced_field.partition(" ")[2]
                header_data.append(replaced_field)

            writer.writerow(header_data)

            for user in queryset_users:
                row = []
                _add_user_fields_to_row(row, fields, user)
                writer.writerow(row)
    else:
        response = HttpResponse(content_type="text/csv")
        writer = csv.writer(response)

        header_data = []
        for field in fields:
            replaced_field = field.replace("_", " ").title()
            if replaced_field.startswith('Dco') or replaced_field.startswith('Dcm') or replaced_field.startswith('Cm'):
                replaced_field = replaced_field.partition(" ")[0].upper() + " " + replaced_field.partition(" ")[2]
            header_data.append(replaced_field)

        writer.writerow(header_data)

        for user in queryset_users:
            row = []
            _add_user_fields_to_row(row, fields, user, orders, all_profiles)
            writer.writerow(row)

        response['Content-Disposition'] = 'attachment; filename="onboarding-users.csv"'
        return response


def _get_user_fields(fields):
    if fields is None:
        return ["id", "name", "profile", "email", "phone", "approval_status", "easyload_number", "sim_pos_code",
                "mfs_number", "robicash_account_number", "agent_banking_number", "store_name", "store_phone", "address",
                "district", "thana", "dco_name", "dco_email", "dcm_name", "dcm_email", "cm_name", "cm_email",
                "location", "agent_banking", "bdtickets", "robicash", "insurance", "el_pos", "sim_pos",
                "collection_point", "device_and_accessories", "iot_and_smart_product", "payment_collection",
                "date_joined"]
    else:
        return fields.split(",")


def _add_user_fields_to_row(row, fields, user, orders, all_profiles):
    user_meta = user.metadata
    for field in fields:
        if field == 'id':
            row.append(get_field_value(user.id))
        if field == 'name':
            row.append(get_field_value(user.get_full_name()))
        if field == 'profile':
            user_orders = list(filter(lambda order: order.user is user, list(orders)))
            row.append(get_field_value(_get_profile(user, user_orders, all_profiles)))
        if field == 'email':
            row.append(get_field_value(user.email))
        if field == 'phone':
            row.append(get_field_value(user.phone))
        if field == 'easyload_number':
            row.append(get_field_value(user_meta.get('easyload_number', '')))
        if field == 'sim_pos_code':
            row.append(get_field_value(user_meta.get('sim_pos_code', '')))
        if field == 'mfs_number':
            row.append(get_field_value(user_meta.get('mfs_number', '')))
        if field == 'robicash_account_number':
            row.append(get_field_value(user_meta.get('robicash_account_number', '')))
        if field == 'agent_banking_number':
            row.append(get_field_value(user_meta.get('agent_banking_number', '')))
        if field == 'store_name':
            row.append(get_field_value(user_meta.get('store_name', '')))
        if field == 'store_phone':
            store_phone = ''
            if user.default_billing_address:
                store_phone = user.default_billing_address.phone
            row.append(store_phone)
        if field == 'address':
            address = user.default_shipping_address.street_address_1 if user.default_shipping_address else None
            row.append(get_field_value(address))
        if field == 'district':
            row.append(get_field_value(",".join([region.district.name for region in user.u_regions])))
        if field == 'thana':
            row.append(get_field_value(",".join([region.thana.name for region in user.u_regions])))

        dco = user.dco
        dcm = user.dcm
        cm = user.cm
        # dco = managers['dco'].get(region)
        # dcm = managers['dcm'].get(region)
        # cm = managers['cm'].get(region)
        if field == 'dco_name':
            if dco:
                row.append(get_field_value(dco.get_full_name()))
            else:
                row.append('N/A')
        if field == 'dco_email':
            if dco:
                row.append(get_field_value(dco.email))
            else:
                row.append('N/A')
        if field == 'dcm_name':
            if dcm:
                row.append(get_field_value(dcm.get_full_name()))
            else:
                row.append('N/A')
        if field == 'dcm_email':
            if dcm:
                row.append(get_field_value(dcm.email))
            else:
                row.append('N/A')
        if field == 'cm_name':
            if cm:
                row.append(get_field_value(cm.get_full_name()))
            else:
                row.append('N/A')
        if field == 'cm_email':
            if cm:
                row.append(get_field_value(cm.email))
            else:
                row.append('N/A')

        if field == 'approval_status':
            row.append(get_field_value(user.approval_status))
        if field == 'location':
            row.append(get_field_value(user_meta.get('location', '')))
        if field == 'agent_banking':
            row.append(get_field_value(user_meta.get('agent_banking', '')))
        if field == 'bdtickets':
            row.append(get_field_value(user_meta.get('bdtickets', '')))
        if field == 'robicash':
            row.append(get_field_value(user_meta.get('robicash', '')))
        if field == 'insurance':
            row.append(get_field_value(user_meta.get('insurance', '')))
        if field == 'el_pos':
            row.append(get_field_value(user_meta.get('el_pos', '')))
        if field == 'sim_pos':
            row.append(get_field_value(user_meta.get('sim_pos', '')))
        if field == 'collection_point':
            row.append(get_field_value(user_meta.get('collection_point', '')))
        if field == 'device_and_accessories':
            row.append(get_field_value(user_meta.get('device_and_accessories', '')))
        if field == 'iot_and_smart_product':
            row.append(get_field_value(user_meta.get('iot_and_smart_product', '')))
        if field == 'payment_collection':
            row.append(get_field_value(user_meta.get('payment_collection', '')))
        if field == 'date_joined':
            row.append(get_field_value(user.created.strftime('%Y-%m-%d')))


def _get_profile(user, orders, all_profiles):
    monthly_totals = dict()

    for profile in all_profiles:
        if monthly_totals.get(profile.period, None):
            result = check_profile_matches(monthly_totals[profile.period], profile)
        else:
            to_date = make_aware(datetime.today().replace(day=1) - timedelta(days=1))
            from_date = to_date + relativedelta(months=-profile.period) + timedelta(days=1)
            # orders_list = orders.filter(user=user, created__range=[from_date, to_date]).distinct()
            orders_list = list(filter(lambda order: from_date <= order.created <= to_date, list(orders)))
            monthly_totals[profile.period] = [sum(x.total_net_amount for x in orders_list), len(orders_list)]
            result = check_profile_matches(monthly_totals[profile.period], profile)
        if result:
            return result
