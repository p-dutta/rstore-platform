import functools
import time

from django.contrib.auth.models import Group
from django.db import reset_queries, connection
from django.http import JsonResponse

from saleor.account.utils import authorize
from saleor.notification import NotificationType
from saleor.notification.models import Notification


# def notify(type):
#     def notify_decorator(function):
#         @functools.wraps(function)
#         def wrapper(*args, **kwargs):
#             if type == NotificationType.PARTNER_ADDED:
#                 function(*args, **kwargs)
#                 notify_partner_added()
#
#         return wrapper
#
#     return notify_decorator
#
#
# def notify_partner_added():
#     agent = Group.objects.get(name='agent')
#     groups = [agent]
#     path = "/partners/"
#     Notification.objects.create_notification(type=NotificationType.PARTNER_ADDED, path=path,
#                                              groups=groups)


def logged_in_required(function):
    def wrap(request, *args, **kwargs):
        # token = request.headers.get("Authorization")
        token = request.GET.get("token")
        if token:
            token = f"JWT {token}"
            delattr(request, "user")
            authorize(request, token)
            if request.user.is_authenticated:
                return function(request, *args, **kwargs)
            else:
                return JsonResponse({"message": "Invalid access token."}, status=401)
        else:
            return JsonResponse({"message": "Token not found."}, status=404)

    return wrap


def query_debugger(func):
    @functools.wraps(func)
    def inner_func(*args, **kwargs):
        reset_queries()

        start_queries = len(connection.queries)

        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()

        end_queries = len(connection.queries)

        print(f"Function : {func.__name__}")
        print(f"Number of Queries : {end_queries - start_queries}")
        print(f"Finished in : {(end - start):.2f}s")
        return result

    return inner_func
