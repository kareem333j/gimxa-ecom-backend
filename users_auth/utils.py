from django.conf import settings

def recored_access_labels(access, user):
    access['_id'] = str(user.id)
    access['username'] = user.username
    access['email'] = user.email
    access['full_name'] = user.full_name
    access['role'] = user.role
    
    return access
    
def set_auth_cookies(response, tokens):
    response.set_cookie(key="access", value=tokens["access"], httponly=True, max_age=settings.ACCESS_TOKEN_LIFETIME_SECONDS, path="/", secure=True, samesite="None")
    response.set_cookie(key="refresh", value=tokens["refresh"], httponly=True, max_age=settings.REFRESH_TOKEN_LIFETIME_SECONDS, path="/", secure=True, samesite="None")