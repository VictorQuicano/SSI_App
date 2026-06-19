from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from auth_app.serializers import VertiportRegistrationSerializer
from auth_app.models import Vertiport
from auth_app.services.vertiport_credential_service import VertiportCredentialService


@csrf_exempt
def vertiport_list_create(request):
    if request.method == 'GET':
        vertiports = Vertiport.objects.all().values(
            'id', 'vertiport_id', 'name', 'location', 'capacity', 'state', 'created_at'
        )
        return JsonResponse({'vertiports': list(vertiports)})

    if request.method == 'POST':
        data = json.loads(request.body)
        serializer = VertiportRegistrationSerializer(data=data)
        if serializer.is_valid():
            vertiport = serializer.save()
            return JsonResponse({'status': 'success', 'vertiport_id': vertiport.id}, status=201)
        return JsonResponse({'status': 'error', 'errors': serializer.errors}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def issue_vertiport_credential(request, vertiport_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        vertiport = Vertiport.objects.get(id=vertiport_id)
    except Vertiport.DoesNotExist:
        return JsonResponse({'error': 'Vertiport no encontrado'}, status=404)

    try:
        svc = VertiportCredentialService()
        record = svc.issue_credential_to_vertiport(vertiport)
        return JsonResponse({
            'status': 'success',
            'credential_exchange_id': record.credential_exchange_id,
            'state': record.state,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_vertiport_credentials(request, vertiport_id):
    try:
        vertiport = Vertiport.objects.get(id=vertiport_id)
    except Vertiport.DoesNotExist:
        return JsonResponse({'error': 'Vertiport no encontrado'}, status=404)

    svc = VertiportCredentialService()
    credentials = svc.get_vertiport_credentials(vertiport)
    data = [{
        'id': c.id,
        'credential_exchange_id': c.credential_exchange_id,
        'state': c.state,
        'attributes': c.attributes,
        'created_at': c.created_at.isoformat(),
    } for c in credentials]
    return JsonResponse({'credentials': data})
