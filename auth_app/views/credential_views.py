from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from auth_app.services.user_credential_service import UserCredentialService
from ..models import CredentialIssuance, User


@csrf_exempt
def issue_user_credential(request):
    """Emitir credencial al usuario autenticado"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)

        required_fields = ['nombres', 'apellidos', 'fecha_nacimiento']
        for field in required_fields:
            if field not in data:
                return JsonResponse(
                    {'error': f'Campo requerido faltante: {field}'},
                    status=400
                )

        # can_ride es decidido por el sistema, no por el cliente
        data.setdefault('can_ride', 'true')

        svc = UserCredentialService()
        credential_record = svc.issue_credential_to_user(request.user, data)

        return JsonResponse({
            'status': 'success',
            'credential_exchange_id': credential_record.credential_exchange_id,
            'state': credential_record.state,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_my_credentials(request):
    """Obtener credenciales del usuario autenticado"""
    user = User.objects.get(id=request.user.id)
    svc = UserCredentialService()
    credentials = svc.get_user_credentials(user)

    data = [{
        'id': cred.id,
        'credential_exchange_id': cred.credential_exchange_id,
        'state': cred.state,
        'attributes': cred.attributes,
        'created_at': cred.created_at.isoformat(),
        'updated_at': cred.updated_at.isoformat(),
    } for cred in credentials]

    return JsonResponse({'credentials': data})


@csrf_exempt
def get_credential_status(request, credential_exchange_id):
    """Obtener estado de una credencial específica"""
    try:
        credential = CredentialIssuance.objects.get(
            credential_exchange_id=credential_exchange_id,
            wallet__object_id=request.user.id,
        )
        return JsonResponse({
            'credential_exchange_id': credential.credential_exchange_id,
            'state': credential.state,
            'attributes': credential.attributes,
            'created_at': credential.created_at.isoformat(),
        })
    except CredentialIssuance.DoesNotExist:
        return JsonResponse({'error': 'Credencial no encontrada'}, status=404)


@csrf_exempt
def credential_webhook(request):
    """Webhook para recibir actualizaciones de estado desde ACA-Py"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        credential_exchange_id = data.get('credential_exchange_id')
        state = data.get('state')

        if credential_exchange_id and state:
            CredentialIssuance.objects.filter(
                credential_exchange_id=credential_exchange_id
            ).update(state=state)

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
