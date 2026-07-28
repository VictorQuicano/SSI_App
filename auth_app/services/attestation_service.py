"""
Trusted Verifier — Opción A de verificación criptográfica SSI → Besu.

Django firma una atestación Ethereum para cada entidad cuya credencial SSI
fue verificada off-chain por ACA-Py. El contrato Besu usa ecrecover() para
comprobar que la firma proviene de esta clave autorizada.

IMPORTANTE — TRABAJO FUTURO:
    Esta implementación es la Opción A (Trusted Verifier). El punto de confianza
    sigue siendo centralizado: quien controla TRUSTED_VERIFIER_KEY puede firmar
    cualquier atestación. Ver docs/10_verificacion_criptografica.md para
    la hoja de ruta hacia las Opciones B (ZK-SNARK) y C (BBS+/secp256k1).
"""

from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

# Clave del verificador de confianza. En producción debería venir de variables
# de entorno y ser diferente a la clave de despliegue de contratos.
TRUSTED_VERIFIER_KEY = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"
TRUSTED_VERIFIER_ADDRESS = Web3.to_checksum_address(
    "0xFE3B557E8Fb62b89F4916B721be55cEb828dBd73"
)


def _sign(msg_hash: bytes) -> str:
    """Firma un hash de 32 bytes con el prefijo EIP-191 y devuelve la firma hex."""
    message = encode_defunct(primitive=msg_hash)
    signed = Account.sign_message(message, private_key=TRUSTED_VERIFIER_KEY)
    return signed.signature.hex()


def sign_user_attestation(rider_address: str, can_ride: bool) -> str:
    """
    Firma la atestación de un usuario.
    Debe coincidir exactamente con el keccak256 en UserVerification.sol:
        keccak256(abi.encodePacked("user", user, canRide))
    """
    msg_hash = Web3.solidity_keccak(
        ["string", "address", "bool"],
        ["user", Web3.to_checksum_address(rider_address), can_ride],
    )
    return _sign(msg_hash)


def sign_vertiport_attestation(vertiport_id: str) -> str:
    """
    Firma la atestación de un vertiport.
    Debe coincidir con: keccak256(abi.encodePacked("vertiport", vertiportId))
    """
    msg_hash = Web3.solidity_keccak(["string", "string"], ["vertiport", vertiport_id])
    return _sign(msg_hash)


def sign_evtol_attestation(evtol_id: int) -> str:
    """
    Firma la atestación de un eVTOL.
    Debe coincidir con: keccak256(abi.encodePacked("evtol", evtolId))
    """
    msg_hash = Web3.solidity_keccak(["string", "uint256"], ["evtol", evtol_id])
    return _sign(msg_hash)
