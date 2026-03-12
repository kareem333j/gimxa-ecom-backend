def get_response_schema_1(status, data=None, message=None, **extra_data):
    if data is None:
        return {
            "message": message,
            "status": status,
            **extra_data
        }
    return {
        "data": data,
        "message": message,
        "status": status,
        **extra_data
    }