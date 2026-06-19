from .base_entity_service import BaseEntityCredentialService
from auth_app.models import CredentialIssuance


class UserCredentialService(BaseEntityCredentialService):

    SCHEMA_NAME    = 'user_credential'
    SCHEMA_VERSION = '2.0'
    SCHEMA_ATTRS   = ['nombres', 'apellidos', 'fecha_nacimiento', 'can_ride']

    def issue_credential_to_user(self, user, user_data: dict) -> CredentialIssuance:
        user_data.setdefault('can_ride', 'true')
        return self.issue_credential(user, user_data)

    def get_user_credentials(self, user, state: str = None):
        return self.get_credentials(user, state)
