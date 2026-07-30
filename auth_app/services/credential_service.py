import time
from auth_app.aca_py.client import ACApyClient
from django.conf import settings


class CredentialService:

    def __init__(self, schema_name: str, schema_version: str, schema_attrs: list):
        self.schema_name = schema_name
        self.schema_version = schema_version
        self.schema_attrs = schema_attrs
        self.client = ACApyClient(settings.ACA_PY_AGENTS['issuer'])

    def get_or_create_schema(self) -> str:
        resp = self.client.get_schemas_created(name=self.schema_name, version=self.schema_version)
        ids = resp.get('schema_ids', [])
        if ids:
            return ids[0]
        result = self.client.create_schema(self.schema_name, self.schema_version, self.schema_attrs)
        return result.get('schema_id') or result.get('sent', {}).get('schema_id')

    def get_or_create_credential_definition(self) -> str:
        schema_id = self.get_or_create_schema()
        resp = self.client.get_credential_definitions_created(schema_id=schema_id)
        ids = resp.get('credential_definition_ids', [])
        if ids:
            return ids[0]
        # el schema puede tardar unos segundos en propagarse entre los nodos Indy
        time.sleep(2)
        result = self.client.create_credential_definition(schema_id, tag='v3')
        return (result.get('credential_definition_id') or
                result.get('sent', {}).get('credential_definition_id'))

    def issue_credential(self, connection_id: str, attributes: dict) -> dict:
        cred_def_id = self.get_or_create_credential_definition()
        attr_list = [{"name": k, "value": str(v)} for k, v in attributes.items()]
        resp = self.client.send_credential_offer(connection_id, cred_def_id, attr_list)
        # v2.0 anida los campos bajo cred_ex_record; normalizamos para que
        # user_credential_service siempre reciba las mismas claves
        record = resp.get('cred_ex_record', resp)
        return {
            'credential_exchange_id': record.get('cred_ex_id') or record.get('credential_exchange_id'),
            'credential_definition_id': cred_def_id,
            'state': record.get('state'),
        }

    def get_credential_records(self, connection_id: str = None, state: str = None) -> dict:
        return self.client.get_issue_credential_records(connection_id, state)
