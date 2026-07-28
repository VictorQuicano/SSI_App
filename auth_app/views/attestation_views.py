from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from auth_app.services.attestation_service import (
    sign_user_attestation,
    sign_vertiport_attestation,
    sign_evtol_attestation,
    TRUSTED_VERIFIER_ADDRESS,
)


@api_view(["POST"])
def attest_user(request):
    """
    Firma una atestación para autorizar a un usuario en Besu.

    Body: {"rider": "0xABC...", "can_ride": true}
    Respuesta: {"signature": "0x...", "verifier": "0x..."}

    En producción: verificar que exista un CredentialIssuance para este rider
    antes de firmar (evita atestaciones para entidades no registradas).
    """
    rider = request.data.get("rider")
    can_ride = request.data.get("can_ride", False)

    if not rider:
        return Response({"error": "rider requerido"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        signature = sign_user_attestation(rider, bool(can_ride))
        return Response({"signature": signature, "verifier": TRUSTED_VERIFIER_ADDRESS})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def attest_vertiport(request):
    """
    Firma una atestación para registrar un vertiport en Besu.

    Body: {"vertiport_id": "vp1-3687"}
    Respuesta: {"signature": "0x...", "verifier": "0x..."}
    """
    vertiport_id = request.data.get("vertiport_id")

    if not vertiport_id:
        return Response({"error": "vertiport_id requerido"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        signature = sign_vertiport_attestation(vertiport_id)
        return Response({"signature": signature, "verifier": TRUSTED_VERIFIER_ADDRESS})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def attest_evtol(request):
    """
    Firma una atestación para registrar un eVTOL en Besu.

    Body: {"evtol_id": 1}
    Respuesta: {"signature": "0x...", "verifier": "0x..."}
    """
    evtol_id = request.data.get("evtol_id")

    if evtol_id is None:
        return Response({"error": "evtol_id requerido"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        signature = sign_evtol_attestation(int(evtol_id))
        return Response({"signature": signature, "verifier": TRUSTED_VERIFIER_ADDRESS})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
