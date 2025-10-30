# services/credential_service.py
from .wallet_service import ACApyClient
from django.conf import settings
import json

class CredentialService:
    def __init__(self):
        self.client = ACApyClient()
    
    def create_dni_schema(self):
        """Crear el esquema para la credencial DNI"""
        schema_name = "DNI"
        schema_version = "1.0"
        attributes = ["nombres", "apellidos", "fecha_nacimiento"]
        
        payload = {
            "attributes": attributes,
            "schema_name": schema_name,
            "schema_version": schema_version
        }
        
        return self.client._make_request('POST', '/schemas', payload)
    
    def create_credential_definition(self, schema_id):
        """Crear definición de credencial basada en el esquema"""
        payload = {
            "schema_id": schema_id,
            "tag": "default",
            "support_revocation": False
        }
        
        return self.client._make_request('POST', '/credential-definitions', payload)
    
    def issue_dni_credential(self, connection_id, user_data):
        """Emitir credencial DNI a un usuario"""
        credential_definition_id = self.get_or_create_dni_credential_def()
        
        # Mapear los datos del usuario a los atributos de la credencial
        attributes = [
            {"name": "nombres", "value": user_data['nombres']},
            {"name": "apellidos", "value": user_data['apellidos']},
            {"name": "fecha_nacimiento", "value": user_data['fecha_nacimiento']}
        ]
        
        payload = {
            "connection_id": connection_id,
            "credential_definition_id": credential_definition_id,
            "attributes": attributes,
            "auto_remove": True,
            "comment": f"Credencial DNI para {user_data['nombres']} {user_data['apellidos']}"
        }
        
        return self.client._make_request('POST', '/issue-credential/send', payload)
    
    def get_or_create_dni_credential_def(self):
        """Obtener o crear la definición de credencial DNI"""
        # Primero verificar si ya existe el esquema
        schemas_response = self.client._make_request('GET', '/schemas/created')
        dni_schemas = [s for s in schemas_response['schema_ids'] if 'DNI' in s]
        
        if not dni_schemas:
            # Crear esquema si no existe
            schema_result = self.create_dni_schema()
            schema_id = schema_result['schema_id']
        else:
            schema_id = dni_schemas[0]
        
        # Verificar si existe la definición de credencial
        cred_defs_response = self.client._make_request('GET', '/credential-definitions/created')
        dni_cred_defs = [cd for cd in cred_defs_response['credential_definition_ids'] if 'DNI' in cd]
        
        if not dni_cred_defs:
            # Crear definición de credencial si no existe
            cred_def_result = self.create_credential_definition(schema_id)
            return cred_def_result['credential_definition_id']
        else:
            return dni_cred_defs[0]
    
    def get_credential_records(self, connection_id=None, state=None):
        """Obtener registros de credenciales"""
        endpoint = '/issue-credential/records'
        params = []
        
        if connection_id:
            params.append(f"connection_id={connection_id}")
        if state:
            params.append(f"state={state}")
        
        if params:
            endpoint += '?' + '&'.join(params)
            
        return self.client._make_request('GET', endpoint)