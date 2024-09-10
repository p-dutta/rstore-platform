import csv
from datetime import datetime, date

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View

from saleor import settings
from saleor.account.views import get_field_value
from saleor.decorators import logged_in_required
from saleor.order import OrderStatus
from saleor.order.models import Order, OrderLine


@method_decorator(logged_in_required, name='get')
class BiExportView(View):
    def get(self, request, *args, **kwargs):
        start_date = request.GET.get("start_date", None)
        end_date = request.GET.get("end_date", None)
        fields = request.GET.get('fields', None)
        return get_bi_data(start_date, end_date, fields)


def get_bi_data(start_date=None, end_date=None, fields=None, bi=False):
    fields = _get_bi_fields(fields)
    orders = Order.objects.all().exclude(status=OrderStatus.CANCELED)
    if not start_date and not end_date:
        today = date.today()
        file_name = f'bi-{today}.csv'
        queryset_orders = orders
    else:
        datetime_start_date = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        datetime_end_time = datetime.strptime(f'{end_date} 23:59:59.999999',
                                              '%Y-%m-%d %H:%M:%S.%f') if end_date else None
        if datetime_start_date and not datetime_end_time:
            queryset_orders = orders.filter(updated__gte=datetime_start_date)
            file_name = str(datetime_start_date.date()) + "_" + ".csv"
        elif datetime_end_time and not datetime_start_date:
            queryset_orders = orders.filter(updated__lte=datetime_end_time)
            file_name = "_" + str(datetime_end_time.date()) + ".csv"
        else:
            queryset_orders = orders.filter(updated__range=[datetime_start_date, datetime_end_time])
            file_name = str(datetime_start_date.date()) + "_" + str(datetime_end_time.date()) + ".csv"

    if bi:
        media_root = settings.MEDIA_ROOT
        bi_file_path = f'{media_root}/bi/{file_name}'

        with open(bi_file_path, 'w', newline='') as file:
            writer = csv.writer(file, delimiter='|')
            header_data = []
            for field in fields:
                replaced_field = field.replace("_", " ").title()
                header_data.append(replaced_field)
            writer.writerow(header_data)
            for order in queryset_orders:
                order_line_items = OrderLine.objects.filter(order=order)
                for item in order_line_items:
                    row = []
                    _add_bi_fields_to_row(row, fields, item)
                    writer.writerow(row)
    else:
        response = HttpResponse(content_type="text/csv")
        writer = csv.writer(response, delimiter=',')

        header_data = []
        for field in fields:
            replaced_field = field.replace("_", " ").title()
            header_data.append(replaced_field)

        writer.writerow(header_data)

        for order in queryset_orders:
            order_line_items = OrderLine.objects.filter(order=order)
            for item in order_line_items:
                row = []
                _add_bi_fields_to_row(row, fields, item)
                writer.writerow(row)

        response['Content-Disposition'] = 'attachment; filename=%s' % file_name
        return response


def _get_bi_fields(fields):
    if fields is None:
        return ["order_line_item_id", "agent_id", "order_id", "partner_id", "partner_order_id", "order_status",
                "payment_status", "type", "currency", "product_sku", "product_name", "category", "unit_price",
                "quantity", "gross_amount", "created", "updated"]
    else:
        return fields.split(",")


def _add_bi_fields_to_row(row, fields, item):
    for field in fields:
        if field == 'order_line_item_id' and fields.__contains__('order_line_item_id'):
            row.append(get_field_value(item.id))
        if field == 'agent_id' and fields.__contains__('agent_id'):
            if item.order.user:
                row.append(get_field_value(item.order.user.id))
            else:
                row.append('N/A')
        if field == 'order_id' and fields.__contains__('order_id'):
            row.append(get_field_value(item.order.id))
        if field == 'partner_id' and fields.__contains__('partner_id'):
            if item.order.partner:
                row.append(get_field_value(item.order.partner.partner_id))
            else:
                row.append('N/A')
        if field == 'partner_order_id' and fields.__contains__('partner_order_id'):
            if item.order.partner:
                row.append(get_field_value(item.order.partner_order_id))
            else:
                row.append('N/A')
        if field == 'order_status' and fields.__contains__('order_status'):
            row.append(get_field_value(item.order.status))
        if field == 'payment_status' and fields.__contains__('payment_status'):
            row.append(get_field_value(item.order.get_payment_status()))
        if field == 'type' and fields.__contains__('type'):
            row.append(get_field_value(item.order.type))
        if field == 'currency' and fields.__contains__('currency'):
            row.append(get_field_value(item.currency))
        if field == 'product_sku' and fields.__contains__('product_sku'):
            row.append(get_field_value(item.product_sku))
        if field == 'product_name' and fields.__contains__('product_name'):
            row.append(get_field_value(item.product_name))
        if field == 'category' and fields.__contains__('category'):
            row.append(get_field_value(item.get_category()))
        if field == 'unit_price' and fields.__contains__('unit_price'):
            row.append(get_field_value(item.unit_price_gross_amount))
        if field == 'quantity' and fields.__contains__('quantity'):
            row.append(get_field_value(item.quantity))
        if field == 'gross_amount' and fields.__contains__('gross_amount'):
            gross_amount = item.quantity * item.unit_price_gross_amount
            row.append(get_field_value(gross_amount))
        if field == 'created' and fields.__contains__('created'):
            row.append(get_field_value(item.created))
        if field == 'updated' and fields.__contains__('updated'):
            row.append(get_field_value(item.updated))
