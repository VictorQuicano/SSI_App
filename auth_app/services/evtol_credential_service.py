from .base_entity_service import BaseEntityCredentialService
from auth_app.models import CredentialIssuance


class EvtolCredentialService(BaseEntityCredentialService):

    SCHEMA_NAME    = 'evtol_credential'
    SCHEMA_VERSION = '3.0'
    SCHEMA_ATTRS   = ['id_puerto', 'state', 'version', 'name', 'can_fly']

    def issue_credential_to_evtol(self, evtol, port_id: str) -> CredentialIssuance:
        attributes = {
            'id_puerto': port_id,
            'name':      evtol.name,
            'state':     evtol.state,
            'version':   evtol.version,
            'can_fly':   str(evtol.can_fly).lower(),
        }
        return self.issue_credential(evtol, attributes)

    def get_evtol_credentials(self, evtol, state: str = None):
        return self.get_credentials(evtol, state)
