# aries-quorum-agent.py
from aries_cloudagent import *
import requests
import json

class QuorumIntegration:
    def __init__(self):
        self.quorum_endpoint = "http://localhost:8545"
        self.bridge_service = "http://localhost:3002"
    
    async def register_did_on_quorum(self, did: str, did_doc: dict):
        """Registrar un DID de Indy en Quorum"""
        payload = {
            "did": did,
            "document": json.dumps(did_doc)
        }
        
        response = requests.post(
            f"{self.bridge_service}/api/register-did",
            json=payload
        )
        return response.json()
    
    async def verify_and_execute_transaction(self, vc_proof: dict, contract_call: dict):
        """Verificar VC y ejecutar transacción en Quorum"""
        payload = {
            "vcProof": vc_proof,
            "contractAddress": contract_call["address"],
            "functionCall": contract_call["function"],
            "parameters": contract_call["parameters"]
        }
        
        response = requests.post(
            f"{self.bridge_service}/api/verify-and-execute",
            json=payload
        )
        return response.json()