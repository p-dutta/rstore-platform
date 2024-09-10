import time
from collections import defaultdict
from datetime import datetime

import pandas as pd
from django.db.models import Q, Count, Prefetch
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View

from saleor.account.models import User, Region
from saleor.account.views import get_field_value
from saleor.decorators import logged_in_required, query_debugger


@method_decorator(logged_in_required, name='get')
class SessionExportView(View):
    def get(self, request, *args, **kwargs):
        user = request.user
        start_date = request.GET.get("start_date", None)
        end_date = request.GET.get("end_date", None)
        fields = request.GET.get('fields', None)
        group = request.GET.get('group', None)
        if not start_date and not end_date:
            return JsonResponse({"message": "Date range is required."}, status=400)
        if not group:
            return JsonResponse({"message": "Group is required."}, status=400)
        return get_session_data(user=user, start_date=start_date, end_date=end_date, fields=fields, group=group)


@query_debugger
def get_session_data(user, start_date, end_date, fields, group):
    fields = _get_session_fields(fields, group)
    fields.append('sessions')

    header_data = dict()
    for field in fields:
        replaced_field = field.replace("_", " ").title()
        header_data[field] = replaced_field

    children_list = user.get_children(False)
    start_time = time.time()
    start_datetime = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
    end_datetime = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
    q = Q()
    if start_datetime and end_datetime:
        q = Q(user_sessions__created__date__gte=start_datetime.date()) & \
            Q(user_sessions__created__date__lte=end_datetime.date())
    session_logs = User.objects.select_related('default_shipping_address').select_related('default_billing_address') \
        .prefetch_related(
        Prefetch(
            'regions', queryset=Region.objects.select_related('district').select_related('thana').all(),
            to_attr='u_regions'
        )
    ).filter(id__in=children_list, groups__name__iexact=group).annotate(sessions=Count('user_sessions__user', filter=q))
    print("--- session_logs %s seconds ---" % (time.time() - start_time))

    if group == 'agent':
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
        for user in session_logs:
            region = user.u_regions[0].pk
            user.dco = managers_dict['dco'].get(region)
            user.dcm = managers_dict['dcm'].get(region)
            user.cm = managers_dict['cm'].get(region)
        print("--- manager assignment %s seconds ---" % (time.time() - start_time))

    start_time = time.time()
    response = HttpResponse(content_type="text/csv")
    df = _prepare_dataframe(session_logs, header_data, group)
    df.to_csv(path_or_buf=response)
    print("--- write %s seconds ---" % (time.time() - start_time))

    file_name = 'session-logs.csv'
    response['Content-Disposition'] = 'attachment; filename=%s' % file_name
    return response


def _prepare_dataframe(data, headers, group):
    csv_data = defaultdict(list)
    for user in data:
        user_meta = user.metadata
        for field in headers.keys():
            if field == 'name':
                csv_data[headers[field]].append(get_field_value(user.get_full_name()))
            if field == 'email':
                csv_data[headers[field]].append(get_field_value(user.email))
            if field == 'phone':
                csv_data[headers[field]].append(get_field_value(user.phone))
            if field == 'approval_status':
                csv_data[headers[field]].append(get_field_value(user.approval_status))
            if field == 'store_name':
                csv_data[headers[field]].append(get_field_value(user_meta.get('store_name', '')))
            if field == 'store_phone':
                store_phone = ''
                if user.default_billing_address:
                    store_phone = user.default_billing_address.phone
                csv_data[headers[field]].append(store_phone)
            if field == 'address':
                address = user.default_shipping_address.street_address_1 if user.default_shipping_address else None
                csv_data[headers[field]].append(get_field_value(address))
            if field == 'district':
                csv_data[headers[field]].append(
                    get_field_value(",".join([region.district.name for region in user.u_regions])))
            if field == 'thana':
                csv_data[headers[field]].append(
                    get_field_value(",".join([region.thana.name for region in user.u_regions])))

            if group == 'agent':
                dco = user.dco
                dcm = user.dcm
                cm = user.cm
                # dco = managers['dco'].get(region)
                # dcm = managers['dcm'].get(region)
                # cm = managers['cm'].get(region)
                if field == 'dco_name':
                    if dco:
                        csv_data[headers[field]].append(get_field_value(dco.get_full_name()))
                    else:
                        csv_data[headers[field]].append('')

                if field == 'dco_email':
                    if dco:
                        csv_data[headers[field]].append(get_field_value(dco.email))
                    else:
                        csv_data[headers[field]].append('')

                if field == 'dcm_name':
                    if dcm:
                        csv_data[headers[field]].append(get_field_value(dcm.get_full_name()))
                    else:
                        csv_data[headers[field]].append('')

                if field == 'dcm_email':
                    if dcm:
                        csv_data[headers[field]].append(get_field_value(dcm.email))
                    else:
                        csv_data[headers[field]].append('')

                if field == 'cm_name':
                    if cm:
                        csv_data[headers[field]].append(get_field_value(cm.get_full_name()))
                    else:
                        csv_data[headers[field]].append('')

                if field == 'cm_email':
                    if cm:
                        csv_data[headers[field]].append(get_field_value(cm.email))
                    else:
                        csv_data[headers[field]].append('')

            if field == 'location':
                csv_data[headers[field]].append(get_field_value(user_meta.get('location', '')))

            if field == 'sessions':
                csv_data[headers[field]].append(get_field_value(user.sessions))

    return pd.DataFrame(csv_data)


agent_fields = ["name", "email", "phone", "approval_status", "store_name", "store_phone", "address",
                "district", "thana", "dco_name", "dco_email", "dcm_name", "dcm_email", "cm_name", "cm_email",
                "location"]

manager_fields = ["name", "email", "phone", "approval_status", "district", "thana", "location"]


def _get_session_fields(fields, group):
    if fields is None:
        if group == 'agent':
            return agent_fields
        else:
            return manager_fields
    else:
        field_list = fields.split(",")
        if group == 'agent':
            return list(filter(lambda v: v in agent_fields, field_list))
        else:
            return list(filter(lambda v: v in manager_fields, field_list))
