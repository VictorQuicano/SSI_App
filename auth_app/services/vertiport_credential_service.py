from .base_entity_service import BaseEntityCredentialService
from auth_app.models import CredentialIssuance


class VertiportCredentialService(BaseEntityCredentialService):

    SCHEMA_NAME    = 'vertiport_credential'
    SCHEMA_VERSION = '4.0'
    SCHEMA_ATTRS   = ['id_vertiport', 'name', 'location', 'capacity', 'state']

    def issue_credential_to_vertiport(self, vertiport) -> CredentialIssuance:
        attributes = {
            'id_vertiport': vertiport.vertiport_id,
            'name':         vertiport.name,
            'location':     vertiport.location,
            'capacity':     str(vertiport.capacity),
            'state':        vertiport.state,
        }
        return self.issue_credential(vertiport, attributes)

    def get_vertiport_credentials(self, vertiport, state: str = None):
        return self.get_credentials(vertiport, state)
