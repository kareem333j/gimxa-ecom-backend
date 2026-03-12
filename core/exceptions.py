# core/exceptions.py
from rest_framework.views import exception_handler
from core.response_schema import get_response_schema_1

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = get_response_schema_1(
            data=None,
            status=response.status_code,
            message=response.data.get('detail', 'Error occurred') if isinstance(response.data, dict) else str(response.data)
        )
    return response
