import ast
import json

from django.conf import settings
from keycloak import KeycloakAdmin, KeycloakOpenID
from keycloak.exceptions import raise_error_from_response, KeycloakGetError
from keycloak.urls_patterns import URL_ADMIN_CLIENT, URL_ADMIN_USER_REALM_ROLES, URL_ADMIN_REALM_ROLES_ROLE_BY_NAME

from .interfaces import AdminConnector, TokenAuthorizer


class KeyCloakAdminConnector(AdminConnector):

    def __init__(self):
        self.keycloak_config = settings.KEYCLOAK_ADMIN_CONFIG
        self.keycloak_admin = KeycloakAdmin(server_url=self.keycloak_config['ADMIN_SERVER_URL'],
                                            client_id=self.keycloak_config['ADMIN_CLI_CLIENT'],
                                            realm_name=self.keycloak_config['ADMIN_REALM_NAME'],
                                            client_secret_key=self.keycloak_config['ADMIN_CLIENT_SECRET'],
                                            auto_refresh_token=['get', 'post', 'put', 'delete'],
                                            verify=True)

    def create_user(self, phone_number: str, password: str, is_enabled: bool, temp_password: bool,
                    groups: list, attributes: dict,
                    email=None, first_name=None, last_name=None, ):
        attributes["phone_number"] = phone_number
        user_info = {
            "email": email,
            "username": phone_number,
            "enabled": is_enabled,
            "firstName": first_name,
            "lastName": last_name,
            "attributes": attributes,
            "groups": groups,
            "credentials": [
                {
                    "value": password,
                    "type": "password",
                    "temporary": temp_password,
                }
            ]

        }

        new_user = self.keycloak_admin.create_user(user_info)
        return new_user

    def count_user(self):
        return self.keycloak_admin.users_count()

    def get_users(self, query=None):
        return self.keycloak_admin.get_users({query})

    def get_user_id_by_username(self, username: str):
        return self.keycloak_admin.get_user_id(username)

    def get_user_by_id(self, user_id: str):
        return self.keycloak_admin.get_user(user_id)

    def update_user(self, user_id: str, params: dict):
        return self.keycloak_admin.update_user(user_id=user_id, payload=params)

    def create_partner(self, data: dict, partner_id: str):
        self.create_client(data)
        client_details = self.get_client_by_name(partner_id)
        client_details['secret'] = self.get_client_secret_by_id(client_details['id'])

        return client_details

    def update_partner(self, data: dict, partner_oidc_id: str):
        self.update_client_by_id(partner_oidc_id, data)
        client_details = self.get_client_by_name(data['name'])

        return client_details

    def create_group(self, payload: dict):
        return self.keycloak_admin.create_group(payload)

    def delete_group(self, group_id: str):
        return self.keycloak_admin.delete_group(group_id)

    def get_groups(self):
        return self.keycloak_admin.get_groups()

    def get_group_by_id(self, group_id: str):
        return self.keycloak_admin.get_group(group_id)

    def get_group_by_name(self, group_name: str):
        return self.keycloak_admin.get_group_by_path(path=group_name, search_in_subgroups=True)

    def group_user_add(self, user_id: str, group_id: str):
        return self.keycloak_admin.group_user_add(user_id, group_id)

    def group_user_remove(self, user_id: str, group_id: str):
        return self.keycloak_admin.group_user_remove(user_id, group_id)

    def get_clients(self):
        return self.keycloak_admin.get_clients()

    def get_client_id(self, client_id: str):
        return self.keycloak_admin.get_client_id(client_id)

    def get_client_role(self, client_id: str, role_name: str):
        return self.keycloak_admin.get_client_role(client_id, role_name)

    def get_client_role_id(self, client_id: str, role_name: str):
        return self.keycloak_admin.get_client_role_id(client_id, role_name)

    def create_client_role(self, client_role_id: str, payload: dict):
        return self.keycloak_admin.create_client_role(client_role_id, payload)

    def assign_client_role(self, user_id: str, client_id: str, roles: list):
        return self.keycloak_admin.assign_client_role(user_id, client_id, roles)

    def create_realm_role(self, payload: dict):
        return self.keycloak_admin.create_realm_role(payload)

    def get_realm_roles(self):
        return self.keycloak_admin.get_realm_roles()

    def assign_realm_roles(self, user_id: str, client_id: str, roles: list):
        return self.keycloak_admin.assign_realm_roles(user_id, client_id, roles)

    def get_group_realm_roles(self, group_id: str):
        return self.keycloak_admin.get_group_realm_roles(group_id)

    def assign_group_realm_roles(self, group_id: str, roles: list):
        return self.keycloak_admin.assign_group_realm_roles(group_id, roles)

    def delete_group_realm_roles(self, group_id: str, roles: list):
        return self.keycloak_admin.delete_group_realm_roles(group_id, roles)

    def get_group_client_roles(self, group_id: str, client_id: str, roles: list):
        return self.keycloak_admin.get_group_client_roles(group_id, client_id, roles)

    def assign_group_client_roles(self, group_id: str, client_id: str, roles: list):
        return self.keycloak_admin.assign_group_client_roles(group_id, client_id, roles)

    def delete_group_client_roles(self, group_id: str, client_id: str, roles: list):
        return self.keycloak_admin.delete_group_client_roles(group_id, client_id, roles)

    def create_client(self, payload: dict):
        return self.keycloak_admin.create_client(payload=payload)

    def get_client_by_name(self, name):
        client_id = self.keycloak_admin.get_client_id(name)
        return self.keycloak_admin.get_client(client_id) if client_id else None

    def get_client_secret_by_id(self, client_id):
        secret = self.keycloak_admin.get_client_secrets(client_id)
        return secret.get('value')

    def update_client_by_id(self, client_id, payload: dict):
        return self.keycloak_admin.update_client(client_id, payload)

    def get_client_scopes(self):
        return self.keycloak_admin.get_client_scopes()

    def add_default_client_scope(self, client_id, scope_id):
        url = self._get_modify_default_scope_url(client_id, scope_id)
        response = self.keycloak_admin.raw_put(url, {})

        return raise_error_from_response(response, KeycloakGetError, expected_codes=[204])

    def delete_default_client_scope(self, client_id, scope_id):
        url = self._get_modify_default_scope_url(client_id, scope_id)
        response = self.keycloak_admin.raw_delete(url, {})

        return raise_error_from_response(response, KeycloakGetError, expected_codes=[204])

    def _get_modify_default_scope_url(self, client_id, scope_id):
        admin_client_params = {"realm-name": self.keycloak_config['ADMIN_REALM_NAME'], "id": client_id}
        return f"{URL_ADMIN_CLIENT.format(**admin_client_params)}/default-client-scopes/{scope_id}"

    def remove_realm_roles(self, user_id: str, client_id: str, roles: list):
        """
        Remove realm roles from a user

        :param user_id: id of user
        :param client_id: id of client containing role (not client-id)
        :param roles: roles list or role (use RoleRepresentation)
        :return Keycloak server response
        """

        payload = roles if isinstance(roles, list) else [roles]
        params_path = {"realm-name": self.keycloak_admin.realm_name, "id": user_id}
        data_raw = self.keycloak_admin.raw_delete(URL_ADMIN_USER_REALM_ROLES.format(**params_path),
                                                  data=json.dumps(payload))
        return raise_error_from_response(data_raw, KeycloakGetError, expected_codes=[204])

    def update_role_by_name(self, role_name, description):
        payload = {'name' : role_name, 'description': description}
        params_path = {"realm-name": self.keycloak_admin.realm_name, "role-name": role_name}
        data_raw = self.keycloak_admin.raw_put(URL_ADMIN_REALM_ROLES_ROLE_BY_NAME.format(**params_path),
                                               data=json.dumps(payload))
        return raise_error_from_response(data_raw, KeycloakGetError, expected_codes=[204])

    def delete_user(self, user_id: str):
        return self.keycloak_admin.delete_user(user_id)


class KeycloakTokenAuthorizer(TokenAuthorizer):

    def __init__(self):
        keycloak_config = settings.KEYCLOAK_ADMIN_CONFIG
        self.keycloak_openid = KeycloakOpenID(
            server_url=keycloak_config['AUTHORIZATION_SERVER_URL'],
            client_id=keycloak_config['AUTHORIZATION_CLIENT_ID'],
            realm_name=keycloak_config['AUTHORIZATION_REALM_NAME'],
            client_secret_key=keycloak_config['AUTHORIZATION_CLIENT_SECRET_KEY']
        )

    def validate_token(self, token):
        return self.keycloak_openid.userinfo(token)

    def token_info(self, token):
        keycloak_public_key = '-----BEGIN PUBLIC KEY-----\n' + \
                              self.keycloak_openid.public_key() + \
                              '\n-----END PUBLIC KEY-----'
        options = {"verify_signature": True, "verify_aud": False, "exp": True}
        return self.keycloak_openid.decode_token(token, key=keycloak_public_key, options=options)
