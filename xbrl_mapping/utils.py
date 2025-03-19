from rest_framework.response import Response
from rest_framework import status

def success_response(message="Operation completed successfully", data=None, status_code=status.HTTP_200_OK):
    """
    Returns a standardized success response
    """
    response_body = {
        "success": True,
        "message": message
    }
    
    if data is not None:
        response_body["data"] = data
    
    return Response(response_body, status=status_code)


def error_response(message="An error occurred", error=None, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Returns a standardized error response
    """
    response_body = {
        "success": False,
        "message": message
    }
    
    if error is not None:
        response_body["error"] = error
    
    return Response(response_body, status=status_code)