from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from auth_app.serializers import EvtolRegistrationSerializer
from auth_app.models import EVTOL
from auth_app.services.evtol_credential_service import EvtolCredentialService


@csrf_exempt
def evtol_list_create(request):
    if request.method == 'GET':
        evtols = EVTOL.objects.all().values(
            'id', 'name', 'model', 'manufacturer', 'serial_number', 'state', 'version', 'can_fly', 'created_at'
        )
        return JsonResponse({'evtols': list(evtols)})

    if request.method == 'POST':
        data = json.loads(request.body)
        serializer = EvtolRegistrationSerializer(data=data)
        if serializer.is_valid():
            evtol = serializer.save()
            return JsonResponse({'status': 'success', 'evtol_id': evtol.id}, status=201)
        return JsonResponse({'status': 'error', 'errors': serializer.errors}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def issue_evtol_credential(request, evtol_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        evtol = EVTOL.objects.get(id=evtol_id)
    except EVTOL.DoesNotExist:
        return JsonResponse({'error': 'eVTOL no encontrado'}, status=404)

    try:
        data = json.loads(request.body)
        port_id = data.get('id_puerto', '')
        svc = EvtolCredentialService()
        record = svc.issue_credential_to_evtol(evtol, port_id=port_id)
        return JsonResponse({
            'status': 'success',
            'credential_exchange_id': record.credential_exchange_id,
            'state': record.state,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_evtol_credentials(request, evtol_id):
    try:
        evtol = EVTOL.objects.get(id=evtol_id)
    except EVTOL.DoesNotExist:
        return JsonResponse({'error': 'eVTOL no encontrado'}, status=404)

    svc = EvtolCredentialService()
    credentials = svc.get_evtol_credentials(evtol)
    data = [{
        'id': c.id,
        'credential_exchange_id': c.credential_exchange_id,
        'state': c.state,
        'attributes': c.attributes,
        'created_at': c.created_at.isoformat(),
    } for c in credentials]
    return JsonResponse({'credentials': data})
