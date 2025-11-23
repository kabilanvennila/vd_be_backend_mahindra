from django.http import JsonResponse
import jwt
from django.conf import settings
from functools import wraps

def jwt_authentication(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        token = request.COOKIES.get('jwt')  # Get the token from the 'jwt' cookie
        if token is not None:
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                request.user_id = payload['user_id']
            except jwt.ExpiredSignatureError:
                return JsonResponse({'error': 'Token has expired'}, status=401)
            except jwt.InvalidTokenError:
                return JsonResponse({'error': 'Invalid token'}, status=401)
        else:
            return JsonResponse({'error': 'Authorization cookie missing'}, status=401)

        return view_func(request, *args, **kwargs)
    return _wrapped_view