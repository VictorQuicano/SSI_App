# views.py
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from auth_app.services.wallet_service import WalletService
from auth_app.models import Wallet, Connection
from auth_app.serializers import UserRegistrationSerializer
from django.views.decorators.csrf import csrf_exempt
import json


@csrf_exempt
def create_user(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    data = json.loads(request.body)
    serializer = UserRegistrationSerializer(data=data)
    if serializer.is_valid():
        user = serializer.save()
        return JsonResponse({'status': 'success', 'user_id': user.id})
    return JsonResponse({'status': 'error', 'errors': serializer.errors}, status=400)


@csrf_exempt
def login_user(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    data = json.loads(request.body)
    user = authenticate(request, username=data.get('username'), password=data.get('password'))
    if user:
        login(request, user)
        return JsonResponse({'status': 'success', 'user_id': user.id})
    return JsonResponse({'error': 'Credenciales inválidas'}, status=401)
