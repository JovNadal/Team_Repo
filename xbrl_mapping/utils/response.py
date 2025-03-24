from rest_framework.response import Response
from rest_framework import status

def success_response(message: str, data=None, status_code=status.HTTP_200_OK):
    """
    Returns a standardized success response
    
    Args:
        message (str): Main success message
        data (dict, optional): Additional data to include in response
        status_code (int, optional): HTTP status code
    
    Returns:
        Response: Django REST Framework Response object
    """
    response_body = {
        "success": True,
        "message": message
    }
    
    if data is not None:
        response_body["data"] = data
    
    return Response(response_body, status=status_code)


def error_response(message: str, error=None, data=None, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Returns a standardized error response
    
    Args:
        message (str): Main error message
        error (str, optional): Error details
        data (dict, optional): Additional data to include in response
        status_code (int, optional): HTTP status code
    
    Returns:
        Response: Django REST Framework Response object
    """
    response_body = {
        "success": False,
        "message": message
    }
    
    if error is not None:
        response_body["error"] = error
        
    if data is not None:
        response_body["data"] = data
    
    return Response(response_body, status=status_code)