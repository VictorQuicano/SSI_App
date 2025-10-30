# views.py
#from django.contrib.auth.decorators import login_required
#from django.http import JsonResponse
#from django.views.decorators.csrf import csrf_exempt
#import json
#from services.dni_service import DNIService
#from ..models import CredentialIssuance, User
#
#@login_required
#def issue_dni_credential(request):
#    """Emitir credencial DNI al usuario autenticado"""
#    if request.method == 'POST':
#        try:
#            data = json.loads(request.body)
#            
#            # Validar datos requeridos
#            required_fields = ['nombres', 'apellidos', 'fecha_nacimiento']
#            for field in required_fields:
#                if field not in data:
#                    return JsonResponse(
#                        {'error': f'Campo requerido faltante: {field}'}, 
#                        status=400
#                    )
#            
#            dni_service = DNIService()
#            credential_record = dni_service.issue_dni_to_user(request.user, data)
#            
#            return JsonResponse({
#                'status': 'success',
#                'credential_exchange_id': credential_record.credential_exchange_id,
#                'state': credential_record.state,
#                'message': 'Credencial DNI emitida exitosamente'
#            })
#            
#        except Exception as e:
#            return JsonResponse({'error': str(e)}, status=500)
#    
#    return JsonResponse({'error': 'Método no permitido'}, status=405)
#
#@csrf_exempt
#def get_my_credentials(request):
#    """Obtener credenciales del usuario autenticado"""
#    user = User.objects.get(id=request.user_id)
#    dni_service = DNIService()
#    credentials = dni_service.get_user_credentials(user)
#    
#    data = [{
#        'id': cred.id,
#        'credential_exchange_id': cred.credential_exchange_id,
#        'state': cred.state,
#        'attributes': cred.attributes,
#        'created_at': cred.created_at,
#        'updated_at': cred.updated_at
#    } for cred in credentials]
#    
#    return JsonResponse({'credentials': data})
#
#@login_required
#def get_credential_status(request, credential_exchange_id):
#    """Obtener estado de una credencial específica"""
#    try:
#        credential = CredentialIssuance.objects.get(
#            credential_exchange_id=credential_exchange_id,
#            user=request.user
#        )
#        
#        return JsonResponse({
#            'credential_exchange_id': credential.credential_exchange_id,
#            'state': credential.state,
#            'attributes': credential.attributes,
#            'created_at': credential.created_at
#        })
#        
#    except CredentialIssuance.DoesNotExist:
#        return JsonResponse({'error': 'Credencial no encontrada'}, status=404)
#
## Webhook para recibir actualizaciones de ACA-Py
#@csrf_exempt
#def credential_webhook(request):
#    """Webhook para recibir actualizaciones de credenciales de ACA-Py"""
#    if request.method == 'POST':
#        try:
#            data = json.loads(request.body)
#            credential_exchange_id = data.get('credential_exchange_id')
#            state = data.get('state')
#            
#            # Actualizar el estado en la base de datos
#            if credential_exchange_id and state:
#                CredentialIssuance.objects.filter(
#                    credential_exchange_id=credential_exchange_id
#                ).update(state=state)
#                
#                print(f"Credencial {credential_exchange_id} actualizada a estado: {state}")
#            
#            return JsonResponse({'status': 'success'})
#            
#        except Exception as e:
#            print(f"Error en webhook de credencial: {e}")
#            return JsonResponse({'error': str(e)}, status=500)
#    
#    return JsonResponse({'error': 'Método no permitido'}, status=405)