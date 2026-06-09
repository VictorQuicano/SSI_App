# services/credential_service.py
from aca_py.client import ACApyClient
from django.conf import settings

# TO DO: Cambiar variables globales para flujo general y no solo flujo de usuario, ponerlo como atributo del metodo init
SCHEMA_NAME    = 'user_credential'
SCHEMA_VERSION = '2.0'
SCHEMA_ATTRS   = ['nombres', 'apellidos', 'fecha_nacimiento', 'can_ride']

class CredentialService:

    def __init__(self):
        issuer_url = settings.ACA_PY_AGENTS['issuer']
        self.client = ACApyClient(issuer_url)

    def get_or_create_schema(self) -> str:
        resp = self.client.get_schemas_created()
        matching = [s for s in resp.get('schema_ids', []) if SCHEMA_NAME in s]
        if matching:
            return matching[0]
        result = self.client.create_schema(SCHEMA_NAME, SCHEMA_VERSION, SCHEMA_ATTRS)
        return result.get('schema_id') or result.get('sent', {}).get('schema_id')

    def get_or_create_credential_definition(self) -> str:
        resp = self.client.get_credential_definitions_created()
        matching = [c for c in resp.get('credential_definition_ids', [])
                    if SCHEMA_NAME in c]
        if matching:
            return matching[0]
        schema_id = self.get_or_create_schema()
        result = self.client.create_credential_definition(schema_id, tag='default')
        return (result.get('credential_definition_id') or
                result.get('sent', {}).get('credential_definition_id'))

    def issue_credential(self, connection_id: str, user_data: dict) -> dict:
        cred_def_id = self.get_or_create_credential_definition()
        attributes = [{"name": k, "value": str(v)} for k, v in user_data.items()]
        return self.client.send_credential_offer(connection_id, cred_def_id, attributes)

    def get_credential_records(self, connection_id: str = None,
                                state: str = None) -> dict:
        return self.client.get_issue_credential_records(connection_id, state)