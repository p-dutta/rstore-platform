from abc import ABCMeta, abstractmethod


class AdminConnector(metaclass=ABCMeta):

    @abstractmethod
    def create_user(self, phone_number: str, password: str, is_enabled: bool, temp_password: bool,
                    groups: list, email: str, attributes: dict,
                    first_name: str, last_name: str):
        pass

    @abstractmethod
    def count_user(self):
        pass

    @abstractmethod
    def get_users(self, query=None):
        pass

    @abstractmethod
    def get_user_id_by_username(self, username: str):
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: str):
        pass

    @abstractmethod
    def update_user(self, user_id: str, params: dict):
        pass

    @abstractmethod
    def create_partner(self, data: dict, partner_id: str):
        pass

    @abstractmethod
    def update_partner(self, data: dict, partner_oidc_id: str):
        pass

    @abstractmethod
    def create_group(self, payload: dict):
        pass

    @abstractmethod
    def delete_group(self, group_id: str):
        pass

    @abstractmethod
    def get_groups(self):
        pass

    @abstractmethod
    def get_group_by_id(self, group_id: str):
        pass

    @abstractmethod
    def get_group_by_name(self, group_name: str):
        pass

    @abstractmethod
    def group_user_add(self, user_id: str, group_id: str):
        pass

    @abstractmethod
    def group_user_remove(self, user_id: str, group_id: str):
        pass

    @abstractmethod
    def get_clients(self):
        pass

    @abstractmethod
    def get_client_id(self, client_id: str):
        pass

    @abstractmethod
    def get_client_role(self, client_id: str, role_name: str):
        pass

    @abstractmethod
    def get_client_role_id(self, client_id: str, role_name: str):
        pass

    @abstractmethod
    def create_client_role(self, client_role_id: str, payload: dict):
        pass

    @abstractmethod
    def assign_client_role(self, user_id: str, client_id: str, roles: list):
        pass

    @abstractmethod
    def create_realm_role(self, payload: dict):
        pass

    @abstractmethod
    def get_realm_roles(self):
        pass

    @abstractmethod
    def assign_realm_roles(self, user_id: str, client_id: str, roles: list):
        pass

    @abstractmethod
    def assign_group_realm_roles(self, group_id: str, roles: list):
        pass

    @abstractmethod
    def delete_group_realm_roles(self, group_id: str, roles: list):
        pass

    @abstractmethod
    def get_group_realm_roles(self, group_id: str):
        pass

    @abstractmethod
    def assign_group_client_roles(self, group_id: str, client_id: str, roles: list):
        pass

    @abstractmethod
    def delete_group_client_roles(self, group_id: str, client_id: str, roles: list):
        pass

    @abstractmethod
    def get_group_client_roles(self, group_id: str, client_id: str, roles: list):
        pass

    @abstractmethod
    def create_client(self, payload: dict):
        pass

    @abstractmethod
    def get_client_by_name(self, name):
        pass

    @abstractmethod
    def get_client_secret_by_id(self, client_id):
        pass

    @abstractmethod
    def update_client_by_id(self, client_id, payload: dict):
        pass

    @abstractmethod
    def get_client_scopes(self):
        pass

    @abstractmethod
    def add_default_client_scope(self, client_id, scope_id):
        pass

    @abstractmethod
    def delete_default_client_scope(self, client_id, scope_id):
        pass

    @abstractmethod
    def remove_realm_roles(self, user_id: str, client_id: str, roles: list):
        pass

    @abstractmethod
    def update_role_by_name(self, role_name, description):
        pass

    @abstractmethod
    def delete_user(self, user_id: str):
        pass


class TokenAuthorizer(metaclass=ABCMeta):

    @abstractmethod
    def validate_token(self, token):
        pass

    @abstractmethod
    def token_info(self, token):
        pass
