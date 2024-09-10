import csv
import os
import random
import string
import time
import pandas as pd

import jwt
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from . import UserApproval
from ..account.error_codes import AccountErrorCode
from ..checkout import AddressType
from ..core import admin_connector, user_cache, token_authorizer
from ..order import OrderStatus
from ..order.models import Order, OrderLine
from ..partner.models import Partner
from ..plugins.manager import get_plugins_manager
from saleor.account.models import Thana, User, Region, SessionLog
from ..product.models import Category, ProductType, Product, ProductVariant

managers_path = os.path.join(
    settings.PROJECT_ROOT, "saleor", "static", "rstore-managers.csv"
)

user_replace_path = os.path.join(
    settings.PROJECT_ROOT, "saleor", "static", "user-replace.csv"
)


def store_user_address(user, address, address_type):
    """Add address to user address book and set as default one."""
    address = get_plugins_manager().change_user_address(address, address_type, user)
    address_data = address.as_data()

    address = user.addresses.filter(**address_data).first()
    if address is None:
        address = user.addresses.create(**address_data)

    if address_type == AddressType.BILLING:
        if not user.default_billing_address:
            set_user_default_billing_address(user, address)
    elif address_type == AddressType.SHIPPING:
        if not user.default_shipping_address:
            set_user_default_shipping_address(user, address)


def set_user_default_billing_address(user, address):
    user.default_billing_address = address
    user.save(update_fields=["default_billing_address"])


def set_user_default_shipping_address(user, address):
    user.default_shipping_address = address
    user.save(update_fields=["default_shipping_address"])


def change_user_default_address(user, address, address_type):
    address = get_plugins_manager().change_user_address(address, address_type, user)
    if address_type == AddressType.BILLING:
        if user.default_billing_address:
            user.addresses.add(user.default_billing_address)
        set_user_default_billing_address(user, address)
    elif address_type == AddressType.SHIPPING:
        if user.default_shipping_address:
            user.addresses.add(user.default_shipping_address)
        set_user_default_shipping_address(user, address)


def create_superuser():
    password = '5xv?EQE8'
    attributes = {}

    email = 'rstore_su@rstore.com.bd'
    phone = '01833184050'
    group = 'admin'
    thana = Thana.objects.filter(name__iexact='Kaliakior').first()
    district = thana.district
    parent = None
    is_superuser = True
    first_name = 'RStore'
    last_name = 'Super'

    keycloak_admin_id = populate_keycloak_user(phone=phone, password=password, email=email, group=group,
                                               first_name=first_name, last_name=last_name,
                                               temp_password=False, attributes=attributes)
    if keycloak_admin_id:
        message, created = populate_rstore_user(phone=phone, email=email, group=group,
                                                district=district, thana=thana, password=password,
                                                first_name=first_name, last_name=last_name,
                                                keycloak_user_id=keycloak_admin_id, is_superuser=is_superuser,
                                                parent=parent)
        yield "Admin: %s/%s/%s %s" % (created.email, created.phone, password, message)
    else:
        yield 'Something went wrong with identity provider'


def transfer_responsibility(email, phone, group, thana, first_name, last_name, old_email):
    password = 'Y&4hraTR'
    thana = get_thana(thana)
    old_user = User.objects.filter(email=old_email).first()
    attributes = {}
    keycloak_id = populate_keycloak_user(phone=phone, password='Y&4hraTR', email=email,
                                         group=group, first_name=first_name, last_name=last_name,
                                         temp_password=False, attributes=attributes)
    if keycloak_id:
        message, user = populate_rstore_user(phone=phone, email=email, group=group, district=thana.district,
                                             first_name=first_name, last_name=last_name, thana=thana,
                                             password='Y&4hraTR',
                                             keycloak_user_id=keycloak_id, parent=old_user.parent)
        yield "User %s/%s/%s has been %s" % (user.email, user.phone, password, message)
    else:
        yield 'Something went wrong with identity provider'

    if old_user:
        regions = old_user.regions.all()
        user.regions.add(*regions)

        children = User.objects.filter(parent=old_user)

        for child in children:
            child.parent = user
            child.save()
            yield "For %s parent %s has been assigned" % (child, user)
    else:
        yield "User with %s not found to transfer children and regions" % old_email


def revoke_access(old_email):
    old_user = User.objects.filter(email=old_email).first()
    if old_user:
        old_user.is_active = False
        old_user.save()
        old_user.delete()
        yield "Access revoked from RStore at %s" % old_user.deleted_at
        keycloak_user_params = {
            "enabled": False,
        }
        try:
            admin_connector.update_user(
                user_id=old_user.oidc_id, params=keycloak_user_params
            )
            yield "Access revoked from Keycloak"
        except Exception as e:
            yield "Something went wrong with identity provider - %s " % e
    else:
        yield "User with %s not found for access revoking" % old_email


def create_opmanagers():
    attributes = {}
    items = [
        ('01819210847', 'shovan@robi.com.bd', 'mgt', 'Robi@123', 'Shovan', 'Chakraborty'),
        ('01819210461', 'riadul.razib@robi.com.bd', 'mgt', 'Robi@123', 'Riadul', 'Hassan Razib'),
        ('01817184638', 'anwar.asad@robi.com.bd', 'mgt', 'Robi@123', 'Md.Anwar', 'Asad'),
        ('01675381845', 'taha.yeasin@robi.com.bd', 'sp', 'Robi@123', 'Md Taha Yeasin', 'Ramadan'),
        ('01611266556', 'arefin.uddin@robi.com.bd', 'sp', 'Robi@123', 'Md.Arefin', 'Uddin'),
    ]

    for item in items:

        keycloak_cm_id = populate_keycloak_user(phone=item[0], password=item[3], email=item[1], group=item[2],
                                                first_name=item[4], last_name=item[5],
                                                temp_password=True, attributes=attributes)
        if keycloak_cm_id:
            message, user = populate_rstore_user(phone=item[0], email=item[1], group=item[2], password=item[3],
                                                 first_name=item[4], last_name=item[5],
                                                 keycloak_user_id=keycloak_cm_id)

            yield "Operational user: %s created" % user.email

        else:
            yield 'Something went wrong with identity provider'


def create_managers():
    attributes = {}
    first_name = 'RStore'

    global admin
    email = 'rstore_su@rstore.com.bd'
    user = User.objects.filter(email=email)
    if user:
        admin = user.first()
    else:
        yield "Admin with email '%s' not found" % email
        return

    items = [
        [
            ('01672977591', 'cm1@rstore.com.bd', 'cm', get_thana('Thanchi'), 'Y&4hraTR'),
            ('01672977593', 'dcm1@rstore.com.bd', 'dcm', get_thana('Thanchi'), 'aSFhX3)u'),
            ('01672977595', 'dco1@rstore.com.bd', 'dco', get_thana('Thanchi'), '?M4Uu87V'),
            ('01672977597', 'agent1@rstore.com.bd', 'agent', get_thana('Thanchi'), 'mg!9)WSS')
        ],
        [
            ('01672977592', 'cm2@rstore.com.bd', 'cm', get_thana('Gowainghat'), '9C(mrB6*'),
            ('01672977594', 'dcm2@rstore.com.bd', 'dcm', get_thana('Gowainghat'), '$9dJV)ys'),
            ('01672977596', 'dco2@rstore.com.bd', 'dco', get_thana('Gowainghat'), 'y7xJ)n8M'),
            ('01672977598', 'agent2@rstore.com.bd', 'agent', get_thana('Gowainghat'), 'kJ(vD!8A')
        ]
    ]

    for item in items:
        cm = item[0]
        dcm = item[1]
        dco = item[2]
        agent = item[3]

        keycloak_cm_id = populate_keycloak_user(phone=cm[0], password=cm[4], email=cm[1], group=cm[2],
                                                first_name=first_name, last_name=cm[2],
                                                temp_password=False, attributes=attributes)
        if keycloak_cm_id:
            message, new_cm = populate_rstore_user(phone=cm[0], email=cm[1], group=cm[2], district=cm[3].district,
                                                   first_name=first_name, last_name=cm[2],
                                                   thana=cm[3], password=cm[4], keycloak_user_id=keycloak_cm_id,
                                                   parent=admin)

            yield "CM: %s/%s/%s %s" % (new_cm.email, new_cm.phone, cm[4], message)
            keycloak_dcm_id = populate_keycloak_user(phone=dcm[0], password=dcm[4], email=dcm[1], group=dcm[2],
                                                     first_name=first_name, last_name=dcm[2],
                                                     temp_password=False, attributes=attributes)
            if keycloak_dcm_id:
                message, new_dcm = populate_rstore_user(phone=dcm[0], email=dcm[1], group=dcm[2],
                                                        district=dcm[3].district,
                                                        first_name=first_name, last_name=dcm[2],
                                                        thana=dcm[3], password=dcm[4], keycloak_user_id=keycloak_dcm_id,
                                                        parent=new_cm)
                yield "DCM: %s/%s/%s %s" % (new_dcm.email, new_dcm.phone, dcm[4], message)
                keycloak_dco_id = populate_keycloak_user(phone=dco[0], password=dco[4], email=dco[1], group=dco[2],
                                                         first_name=first_name, last_name=dco[2],
                                                         temp_password=False, attributes=attributes)
                if keycloak_dco_id:
                    message, new_dco = populate_rstore_user(phone=dco[0], email=dco[1], group=dco[2],
                                                            district=dco[3].district, thana=dco[3], password=dco[4],
                                                            first_name=first_name, last_name=dco[2],
                                                            keycloak_user_id=keycloak_dco_id,
                                                            parent=new_dcm)
                    yield "DCO: %s/%s/%s %s" % (new_dco.email, new_dco.phone, dco[4], message)
                    keycloak_agent_id = populate_keycloak_user(phone=agent[0], password=agent[4], email=agent[1],
                                                               first_name=first_name, last_name=agent[2],
                                                               group=agent[2], temp_password=False,
                                                               attributes=attributes)
                    if keycloak_agent_id:
                        message, new_agent = populate_rstore_user(phone=agent[0], email=agent[1], group=agent[2],
                                                                  district=agent[3].district, thana=agent[3],
                                                                  password=agent[4],
                                                                  first_name=first_name, last_name=agent[2],
                                                                  keycloak_user_id=keycloak_agent_id,
                                                                  parent=new_dco)
                        yield "Agent: %s/%s/%s %s" % (new_agent.email, new_agent.phone, agent[4], message)
                    else:
                        yield 'Something went wrong with identity provider'
                else:
                    yield 'Something went wrong with identity provider'
            else:
                yield 'Something went wrong with identity provider'
        else:
            yield 'Something went wrong with identity provider'


def get_thana(name):
    thana = Thana.objects.filter(name__iexact=name).first()
    return thana


def import_managers():
    attributes = {}
    password = '@rSt0R3'
    with open(managers_path, 'r') as read_obj:
        csv_reader = csv.reader(read_obj)
        next(csv_reader)
        for row in csv_reader:
            group = row[0].strip()
            email = row[1].strip()
            phone = row[2].strip()
            first_name = row[3].strip()
            last_name = row[4].strip()

            thanas = row[5].split(",")
            keycloak_id = populate_keycloak_user(phone=phone, password=password, first_name=first_name,
                                                 last_name=last_name, email=email, group=group.lower(),
                                                 temp_password=True, attributes=attributes)
            if keycloak_id:
                parent = User.objects.filter(phone=row[6]).first()
                thana = Thana.objects.filter(
                    Q(name__iexact=thanas[0].strip()) | Q(name__istartswith=thanas[0].strip())
                ).first()
                message, user = populate_rstore_user(phone=phone, email=email, group=group.lower(),
                                                     district=thana.district, first_name=first_name,
                                                     last_name=last_name, thana=thana, password=password,
                                                     keycloak_user_id=keycloak_id,
                                                     parent=parent)
                yield "%s: %s/%s/%s %s" % (group, user.email, user.phone, password, message)
            for item in thanas[1:]:
                thana = Thana.objects.filter(
                    Q(name__iexact=item.strip()) | Q(name__istartswith=item.strip())
                ).first()
                User.objects.set_region(district=thana.district, thana=thana, user=user)


def populate_rstore_user(phone, email, group, password, keycloak_user_id, first_name,
                         last_name, parent=None, district=None, thana=None, is_superuser=False):
    user = User.objects.filter(email__iexact=email)
    if user:
        user = user.first()
        user.oidc_id = keycloak_user_id
        user.save()
        message = 'Already Exists. OIDC information updated'
        return message, user
    else:
        user = User.objects.create_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            password=password,
            user_group=group,
            district=district,
            thana=thana,
            approval_status='approved',
            is_superuser=is_superuser,
            keycloak_user_id=keycloak_user_id,
            parent=parent,
        )
        message = 'Created'
        return message, user


def populate_keycloak_user(phone, password, email, group, attributes, temp_password, first_name=None, last_name=None):
    keycloak_user_id = admin_connector.create_user(
        first_name=first_name,
        last_name=last_name,
        phone_number=phone,
        email=email,
        is_enabled=True,
        password=password,
        temp_password=temp_password,
        groups=[group],
        attributes=attributes
    )
    return keycloak_user_id


def add_replace_managers():
    password = '@rSt0R3'
    df = pd.read_csv(user_replace_path, dtype=str)
    for i in range(len(df)):
        email = df.loc[i, 'Email']
        phone = df.loc[i, 'Proposed Number']
        group = df.loc[i, 'Group']
        first_name = df.loc[i, 'Proposed First Name']
        last_name = df.loc[i, 'Proposed Last Name']
        staff = User.objects.filter(email=email)
        if staff.exists():
            staff = staff.first()
            parent = staff.parent
            children = User.objects.filter(parent=staff)
            regions = staff.regions.all()
            remove_staff_member(staff)
        else:
            parent_email = None
            if group == 'DCO':
                parent_email = df.loc[i, 'DCM Email Address']
            elif group == 'DCM':
                parent_email = df.loc[i, 'CM Email Address']
            parent = None
            if parent_email:
                parent = User.objects.filter(email=parent_email).first()
            children = None
            regions = None
        try:
            keycloak_user_id = populate_keycloak_user(phone=phone, password=password, first_name=first_name,
                                                      last_name=last_name, email=email, group=group.lower(),
                                                      temp_password=True, attributes={})
            if keycloak_user_id:
                message, user = populate_rstore_user(phone=phone, email=email, group=group.lower(), district=None,
                                                     thana=None, first_name=first_name, last_name=last_name,
                                                     password=password, keycloak_user_id=keycloak_user_id,
                                                     parent=parent)
                if regions:
                    user.regions.add(*regions)
                if children:
                    for child in children:
                        child.parent = user
                    User.objects.bulk_update(children, ['parent'])
                yield "%s: %s/%s/%s %s" % (group, user.email, user.phone, password, message)
        except Exception as e:
            print(e)
            yield "Something went wrong with identity provider. email: %s" % email


def replace_removed_managers():
    password = '@rSt0R3'
    df = pd.read_csv(user_replace_path, dtype=str)
    for i in range(len(df)):
        email = df.loc[i, 'Email']
        phone = df.loc[i, 'Proposed Number']
        group = df.loc[i, 'Group']
        first_name = df.loc[i, 'Proposed First Name']
        last_name = df.loc[i, 'Proposed Last Name']
        staff = User.raw_objects.filter(email=email)
        if staff.exists():
            staff = staff.latest('created')
            parent = staff.parent
            children = User.objects.filter(parent=staff)
            regions = staff.regions.all()
            try:
                keycloak_user_id = populate_keycloak_user(phone=phone, password=password, first_name=first_name,
                                                          last_name=last_name, email=email, group=group.lower(),
                                                          temp_password=True, attributes={})
                if keycloak_user_id:
                    message, user = populate_rstore_user(phone=phone, email=email, group=group.lower(), district=None,
                                                         thana=None, first_name=first_name, last_name=last_name,
                                                         password=password, keycloak_user_id=keycloak_user_id,
                                                         parent=parent)
                    if regions:
                        user.regions.add(*regions)
                    if children:
                        for child in children:
                            child.parent = user
                        User.objects.bulk_update(children, ['parent'])
                    yield "%s: %s/%s/%s %s" % (group, user.email, user.phone, password, message)
            except Exception as e:
                print(e)
                yield "Something went wrong with identity provider. email: %s" % email


def remove_staff_member(staff):
    try:
        admin_connector.delete_user(user_id=staff.oidc_id)
    except Exception as e:
        print(e)
        return False
    staff.is_active = False
    staff.delete()

    return True


def create_jwt_token(token_data):
    expiration_date = timezone.now() + timezone.timedelta(hours=1)
    token_kwargs = {"exp": expiration_date}
    token_kwargs.update(token_data)
    token = jwt.encode(token_kwargs, settings.SECRET_KEY, algorithm="HS256").decode()
    return token


def decode_jwt_token(token):
    try:
        decoded_token = jwt.decode(
            token.encode(), settings.SECRET_KEY, algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        raise ValidationError(
            {
                "token": ValidationError(
                    "Invalid or expired token.", code=AccountErrorCode.INVALID
                )
            }
        )
    return decoded_token


def authorize(request, token=None):
    if not hasattr(request, 'user'):
        full_token = request.META.get('HTTP_AUTHORIZATION', token)
        if full_token:
            auth = full_token.split()
            if len(auth) == 2 and auth[0] == 'JWT':
                access_token = auth[1]
                if user_cache.has(access_token):
                    request.user = User.objects.get(pk=user_cache.get(access_token))
                else:
                    try:
                        token_authorizer.validate_token(access_token)
                        token_info = token_authorizer.token_info(access_token)
                        request.user = User.objects.get(oidc_id=token_info['sub'])
                        SessionLog.objects.create(user=request.user)
                        ttl = token_info['exp'] - int(round(time.time()))
                        if not user_cache.has(access_token):
                            user_cache.add(key=access_token, value=request.user.pk, ttl=ttl)
                    except Exception as e:
                        print(e)
                        if not hasattr(request, 'user') or request.user is None:
                            request.user = AnonymousUser()
            else:
                request.user = AnonymousUser()
        else:
            request.user = AnonymousUser()


def create_dummy_users():
    thanas = Thana.objects.all()
    size = 20000
    for i in range(size):
        first_name = f"{''.join(random.choices(string.ascii_lowercase, k=8))}"
        print(first_name)
        last_name = f"{''.join(random.choices(string.ascii_lowercase, k=8))}"
        print(last_name)
        email = f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}@rstore.com.bd"
        print(email)
        phone = f"01{''.join(random.choices(string.digits, k=9))}"
        print(phone)
        store_name = f"{''.join(random.choices(string.ascii_letters + string.digits, k=6))} Store"
        print(store_name)
        address = f"{''.join(random.choices(string.ascii_letters + string.digits, k=50))}"
        print(address)
        thana = random.choice(thanas)
        print(thana)
        keycloak_user_id = f"{''.join(random.choices(string.ascii_letters + string.digits, k=16))}"
        print(keycloak_user_id)
        user = User.objects.create_user(phone=phone, email=email, first_name=first_name, last_name=last_name,
                                        address=address, district=thana.district, thana=thana,
                                        keycloak_user_id=keycloak_user_id, metadata={'store_name': store_name},
                                        approval_status=UserApproval.APPROVED)

        yield f'{user} created successfully'


def create_dummy_sessions():
    users = User.objects.all()
    count = users.count()
    size = 100000
    sessions = []
    for i in range(size):
        pk = random.randrange(1, count)
        print(pk)
        user = users.filter(pk=pk).first()
        if user:
            sessions.append(SessionLog(user=user))

    SessionLog.objects.bulk_create(sessions)

    yield f'{size} session logs created successfully'


def create_dummy_products():
    partners = Partner.objects.all()
    pacount = partners.count()
    categories = Category.objects.all()
    ccount = categories.count()
    product_type = ProductType.objects.get(pk=1)
    size = 100

    products = []
    for i in range(size):
        name = f"{''.join(random.choices(string.ascii_lowercase, k=10))}"
        partner = partners[random.randrange(1, pacount)]
        products.append(Product(
            name=f"{''.join(random.choices(string.ascii_lowercase, k=10))}",
            description=f"{''.join(random.choices(string.ascii_lowercase, k=20))}",
            price_amount=random.randrange(100, 500),
            product_type=product_type,
            is_published=True,
            category=categories[random.randrange(1, ccount)],
            charge_taxes=True,
            currency='BDT',
            partner=partner,
            slug=f'{name}-{partner.partner_id}'
        ))
    Product.objects.bulk_create(products)
    print('Products created')

    variants = []
    for product in products:
        variants.append(ProductVariant(
            sku=f'{partners[random.randrange(1, pacount)].partner_id}-{random.randrange(1000, 5000)}',
            name=product.name,
            price_override_amount=product.price_amount,
            product=product,
            track_inventory=True,
            currency='BDT'
        ))
    ProductVariant.objects.bulk_create(variants)
    print('Variants created')

    yield f'{size} products created successfully'


def create_dummy_orders():
    users = User.objects \
        .select_related('default_billing_address') \
        .select_related('default_shipping_address') \
        .all()
    ucount = users.count()
    partners = Partner.objects.all()
    pacount = partners.count()
    size = 5000

    variants = ProductVariant.objects \
        .select_related('product') \
        .select_related('product__partner') \
        .all()
    vcount = variants.count()

    status = [
        OrderStatus.FULFILLED,
        OrderStatus.UNFULFILLED,
        OrderStatus.CANCELED,
    ]
    orders = []
    for i in range(size):
        user = users[random.randrange(1, ucount)]
        partner = partners[random.randrange(1, pacount)]
        token = f"{''.join(random.choices(string.ascii_lowercase, k=24))}"
        print(token)
        orders.append(Order(
            token=token,
            billing_address=user.default_billing_address,
            shipping_address=user.default_shipping_address,
            user=user,
            status=status[random.randrange(1, 3)],
            currency='BDT',
            partner=partner,
            partner_order_id=f"{''.join(random.choices(string.ascii_lowercase, k=6))}",
            total_net_amount=random.randrange(100, 1000)
        ))
    Order.objects.bulk_create(orders)
    print('Orders created')

    lines = []
    for order in orders:
        for i in range(random.randrange(1, 5)):
            variant = variants[random.randrange(1, vcount)]
            print(variant.name)
            lines.append(OrderLine(
                product_name=variant.name,
                product_sku=variant.sku,
                quantity=random.randrange(1, 5),
                unit_price_net_amount=variant.price_override_amount,
                unit_price_gross_amount=variant.price_override_amount,
                is_shipping_required=True,
                order=order,
                variant=variant,
                currency='BDT',
                variant_name=variant.name
            ))
    OrderLine.objects.bulk_create(lines)
    print('Order lines created')

    yield f'{size} orders created successfully'
