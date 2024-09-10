import csv
import time
from collections import defaultdict
from datetime import datetime

import graphene
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View

from saleor.account.models import User, Region
from saleor.account.views import get_field_value
from saleor.decorators import logged_in_required, query_debugger
from saleor.order.models import Order
from saleor.partner.models import Partner


@method_decorator(logged_in_required, name='get')
class AgentPartnerView(View):

    def get(self, request, *args, **kwargs):
        start_date = request.GET.get("start_date", None)
        end_date = request.GET.get("end_date", None)
        fields = request.GET.get('fields', None)
        partner_ids = request.GET.get('partner_ids', None)

        if not start_date:
            return JsonResponse({"message": "Start date is required."}, status=400)
        if not end_date:
            return JsonResponse({"message": "End date is required."}, status=400)
        if not partner_ids:
            return JsonResponse({"message": "List of partner IDs is required."}, status=400)

        try:
            datetime_start_date = datetime.strptime(start_date, '%Y-%m-%d')
            datetime_end_date = datetime.strptime(f'{end_date} 23:59:59.999999', '%Y-%m-%d %H:%M:%S.%f')
        except ValueError as e:
            return JsonResponse({"message": str(e)}, status=400)

        return get_transaction_data(datetime_start_date, datetime_end_date, partner_ids, fields)


@query_debugger
def get_transaction_data(start_date, end_date, partner_ids, fields):
    fields = _get_user_fields(fields)

    start_time = time.time()
    partner_ids = partner_ids.split(",")
    partner_local_ids = []
    for pid in partner_ids:
        _, pid = graphene.Node.from_global_id(pid)
        partner_local_ids.append(pid)

    partners = Partner.objects.filter(id__in=partner_local_ids)
    print("--- partners %s seconds ---" % (time.time() - start_time))

    response = HttpResponse(content_type="text/csv")
    writer = csv.writer(response)

    header_data = []
    for field in fields:
        replaced_field = field.replace("_", " ").title()
        header_data.append(replaced_field)

    for partner in partners:
        name = partner.partner_name.title()
        header_data.append(name)

    writer.writerow(header_data)

    start_time = time.time()
    user_orders = User.objects.select_related('default_shipping_address').select_related('default_billing_address') \
        .prefetch_related(
        Prefetch('groups', to_attr='u_groups')
    ).prefetch_related(
        Prefetch(
            'regions', queryset=Region.objects.select_related('district').select_related('thana').all(),
            to_attr='u_regions'
        )
    ).prefetch_related(
        Prefetch(
            'orders', queryset=Order.objects.select_related('partner')
                .filter(created__gte=start_date, created__lte=end_date, partner__isnull=False),
            to_attr='u_orders'
        )
    ).filter(groups__name="agent")
    print("--- user_orders %s seconds ---" % (time.time() - start_time))

    start_time = time.time()
    managers = User.objects.prefetch_related(
        Prefetch('groups', to_attr='u_groups')
    ).prefetch_related(
        Prefetch('regions', to_attr='u_regions')
    ).filter(groups__name__in=['dco', 'dcm', 'cm'])
    print("--- manager query %s seconds ---" % (time.time() - start_time))
    start_time = time.time()
    managers_dict = defaultdict(dict)
    for manager in managers:
        regions = manager.u_regions
        u_group = manager.u_groups[0]
        for region in regions:
            managers_dict[u_group.name][region.pk] = manager
    print("--- manager_dict %s seconds ---" % (time.time() - start_time))

    start_time = time.time()
    for user in user_orders:
        region = user.u_regions[0].pk
        user.dco = managers_dict['dco'].get(region)
        user.dcm = managers_dict['dcm'].get(region)
        user.cm = managers_dict['cm'].get(region)
    print("--- manager assignment %s seconds ---" % (time.time() - start_time))

    start_time = time.time()
    for user in user_orders:
        orders = user.u_orders
        # print(orders)
        if len(orders):
            row = []
            _add_user_fields_to_row(row, fields, user)

            order_amounts = {}
            for order in orders:
                partner_id = order.partner.partner_id
                order_amounts[partner_id] = order_amounts.get(partner_id, 0) + order.total_net_amount
            for partner in partners:
                amount = order_amounts.get(partner.partner_id, 0)
                row.append(amount)

            writer.writerow(row)
    print("--- user order assign %s seconds ---" % (time.time() - start_time))

    response['Content-Disposition'] = 'attachment; filename="agent-partner-transactions.csv"'
    return response


def _get_user_fields(fields):
    if fields is None:
        return ["name", "email", "phone", "address", "district", "thana", "approval_status",
                "dco_name", "dco_email", "dcm_name", "dcm_email", "cm_name", "cm_email",
                "store_name", "store_phone", "sim_pos_code", "location", "date_joined"]
    else:
        return fields.split(",")


def _add_user_fields_to_row(row, fields, user):
    user_meta = user.metadata
    # region = user.u_regions[0].pk
    for field in fields:
        if field == 'name':
            row.append(get_field_value(user.get_full_name()))
        if field == 'email':
            row.append(get_field_value(user.email))
        if field == 'phone':
            row.append(get_field_value(user.phone))
        if field == 'approval_status':
            row.append(get_field_value(user.approval_status))
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
        if field == 'location':
            row.append(get_field_value(user_meta.get('location', '')))
        if field == 'sim_pos_code':
            row.append(get_field_value(user_meta.get('sim_pos_code', '')))
        if field == 'date_joined':
            row.append(get_field_value(user.created.strftime('%Y-%m-%d')))
