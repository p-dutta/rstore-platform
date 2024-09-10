import csv
from collections import defaultdict
from datetime import datetime, date
from time import time

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View

from saleor.account.models import User, Region
from saleor.account.views import get_field_value
from saleor.decorators import logged_in_required
from saleor.order import OrderStatus
from saleor.order.models import Order, OrderLine
from saleor.product.models import CategoryAttribute
from saleor.decorators import logged_in_required, query_debugger
from django.db.models import Q, Prefetch


@method_decorator(logged_in_required, name='get')
class PerformanceExportView(View):
    def get(self, request, *args, **kwargs):
        user = request.user
        start_date = request.GET.get("start_date", None)
        end_date = request.GET.get("end_date", None)
        fields = request.GET.get('fields', None)
        attributes = request.GET.get('attributes', None)
        return get_performance_data(user=user, start_date=start_date, end_date=end_date, fields=fields,
                                    attributes=attributes)


@query_debugger
def get_performance_data(user=None, start_date=None, end_date=None, fields=None, attributes=None):
    start = time()
    fields = _get_performance_fields(fields)
    attributes = _get_performance_attributes(attributes)

    response = HttpResponse(content_type="text/csv")
    writer = csv.writer(response, delimiter=',')

    for attribute in attributes:
        fields.append(attribute)

    header_data = []
    for field in fields:
        replaced_field = field.replace("_", " ").title()
        header_data.append(replaced_field)

    writer.writerow(header_data)
    order_line_items = OrderLine.objects.all()
    category_attributes = CategoryAttribute.objects.all()
    children_list = user.get_children(False)

    datetime_start_date = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
    datetime_end_time = datetime.strptime(f'{end_date} 23:59:59.999999',
                                          '%Y-%m-%d %H:%M:%S.%f') if end_date else None
    file_name = str(datetime_start_date.date()) + "_" + str(datetime_end_time.date()) + ".csv"

    query_cond = Q(user__id__in=children_list) & Q(user__isnull=False) & \
                 Q(user__groups__name="agent") & Q(updated__range=[datetime_start_date, datetime_end_time])

    filtered_orders = Order.objects.select_related('user__default_billing_address') \
        .select_related('user__default_shipping_address').prefetch_related(
        Prefetch(
            'user__regions',
            queryset=Region.objects.select_related('district').select_related('thana').all(),
            to_attr='u_regions'
        )
    ).filter(query_cond).exclude(status=OrderStatus.CANCELED)

    order_user_ids = filtered_orders.values_list('user', flat=True)

    count = 0
    for user_id in set(order_user_ids):
        count += 1
        user_orders = filtered_orders.filter(user=user_id)

        attribute_map = {}
        attribute_map = defaultdict(lambda: 0, attribute_map)

        for order in user_orders:
            line_items = order_line_items.filter(order=order)
            for item in line_items:
                for attribute in attributes:
                    category_attribute = category_attributes.filter(slug=attribute).first()
                    if category_attribute:
                        attribute_categories = category_attribute.categories.all()
                        for attribute_category in attribute_categories:
                            if attribute_category == item.get_category():
                                total = item.unit_price_net_amount * item.quantity
                                attribute_map[attribute] = attribute_map[attribute] + total
            user = order.user
        if len(attribute_map) != 0:
            row = []
            _add_performance_fields_to_row(row=row, user=user, fields=fields, attributes=attributes,
                                           attribute_map=attribute_map)
            writer.writerow(row)

    print(f'loop ran {count} times')
    print(f'outer loop ends: {time() - start} seconds')
    response['Content-Disposition'] = 'attachment; filename=%s' % file_name
    return response


def _add_performance_fields_to_row(row, fields, user, attributes, attribute_map):
    user_meta = user.metadata
    for field in fields:
        if field == 'name' and fields.__contains__('name'):
            row.append(get_field_value(user.get_full_name()))
        if field == 'email' and fields.__contains__('email'):
            row.append(get_field_value(user.email))
        if field == 'phone' and fields.__contains__('phone'):
            row.append(get_field_value(user.phone))
        if field == 'approval_status' and fields.__contains__('approval_status'):
            row.append(get_field_value(user.approval_status))
        if field == 'store_name' and fields.__contains__('store_name'):
            row.append(get_field_value(user_meta.get('store_name', '')))
        if field == 'store_phone' and fields.__contains__('store_phone'):
            store_phone = ''
            if user.default_billing_address:
                store_phone = user.default_billing_address.phone
            row.append(store_phone)
        if field == 'address' and fields.__contains__('address'):
            address = user.default_shipping_address.street_address_1 if user.default_shipping_address else None
            row.append(get_field_value(address))
        if field == 'district' and fields.__contains__('district'):
            row.append(get_field_value(",".join([region.district.name for region in user.u_regions])))
        if field == 'thana' and fields.__contains__('thana'):
            row.append(get_field_value(",".join([region.thana.name for region in user.u_regions])))

        if field == 'dco_name' and fields.__contains__('dco_name'):
            agent_region = user.regions.first()
            dco = User.objects.get_dco_by_region(agent_region)
            if dco:
                row.append(get_field_value(dco.get_full_name()))
            else:
                row.append('N/A')
        if field == 'dco_email' and fields.__contains__('dco_email'):
            if dco is None:
                if agent_region is None:
                    agent_region = user.regions.first()
                dco = User.objects.get_dco_by_region(agent_region)
            if dco:
                row.append(get_field_value(dco.email))
            else:
                row.append('N/A')

        if field == 'dcm_name' and fields.__contains__('dcm_name'):
            if agent_region is None:
                agent_region = user.regions.first()
            dcm = User.objects.get_dcm_by_region(agent_region)
            if dcm:
                row.append(get_field_value(dcm.get_full_name()))
            else:
                row.append('N/A')
        if field == 'dcm_email' and fields.__contains__('dcm_email'):
            if dcm is None:
                if agent_region is None:
                    agent_region = user.regions.first()
                dcm = User.objects.get_dcm_by_region(agent_region)
            if dcm:
                row.append(get_field_value(dcm.email))
            else:
                row.append('N/A')

        if field == 'cm_name' and fields.__contains__('cm_name'):
            if agent_region is None:
                agent_region = user.regions.first()
            cm = User.objects.get_cm_by_region(agent_region)
            if cm:
                row.append(get_field_value(cm.get_full_name()))
            else:
                row.append('N/A')
        if field == 'cm_email' and fields.__contains__('cm_email'):
            if cm is None:
                if agent_region is None:
                    agent_region = user.regions.first()
                cm = User.objects.get_cm_by_region(agent_region)
            if cm:
                row.append(get_field_value(cm.email))
            else:
                row.append('N/A')

        if field == 'location' and fields.__contains__('location'):
            row.append(get_field_value(user_meta.get('location', '')))
        if field == 'sim_pos_code' and fields.__contains__('sim_pos_code'):
            row.append(get_field_value(user_meta.get('sim_pos_code', '')))
        if field == 'date_joined' and fields.__contains__('date_joined'):
            row.append(get_field_value(user.created.strftime('%Y-%m-%d')))

    for attribute in attributes:
        if attribute in attribute_map:
            row.append(attribute_map[attribute])
        else:
            row.append(0.0)


def _get_performance_fields(fields):
    if fields is None:
        return ["name", "email", "phone", "approval_status", "store_name", "store_phone", "address",
                "district", "thana", "dco_name", "dco_email", "dcm_name", "dcm_email", "cm_name", "cm_email",
                "location", "sim_pos_code", "date_joined"]
    else:
        return fields.split(",")


def _get_performance_attributes(attributes):
    if attributes is None:
        attributes = []
        category_attributes = CategoryAttribute.objects.all()
        for item in category_attributes:
            attributes.append(item.slug)
        return attributes
    else:
        return attributes.split(",")
