from rest_framework.response import Response
from rest_framework import status
from typing import Dict, List, Any, Optional, Union
import json
import logging
from .serializers import XBRLValidationSerializer

logger = logging.getLogger(__name__)

def success_response(message: str = "XBRL data is valid", data: Optional[Dict] = None) -> Response:
    """
    Generate a standardized success response.
    
    Args:
        message: Success message to include in response
        data: Optional data to include in the response
        
    Returns:
        DRF Response with success status
    """
    response_data = {
        'success': True,
        'message': message
    }
    
    if data:
        response_data['data'] = data
        
    return Response(response_data, status=status.HTTP_200_OK)

def error_response(
    message: str,
    errors: Optional[Union[List[Dict[str, str]], Dict[str, List[str]]]] = None,
    status_code: int = status.HTTP_400_BAD_REQUEST
) -> Response:
    """
    Generate a standardized error response.
    
    Args:
        message: Error message to include in response
        errors: Validation errors (can be list or dict format)
        status_code: HTTP status code for response
        
    Returns:
        DRF Response with error status
    """
    response_data = {
        'success': False,
        'message': message
    }
    
    if errors:
        # Handle dictionary of errors by section
        if isinstance(errors, dict):
            formatted_errors = format_validation_errors(errors)
            response_data['error_count'] = len(formatted_errors)
            response_data['errors'] = formatted_errors
        # Handle pre-formatted list of errors
        elif isinstance(errors, list):
            response_data['error_count'] = len(errors)
            response_data['errors'] = errors
            
    logger.debug(f"Returning error response: {response_data}")
    return Response(response_data, status=status_code)

def format_validation_errors(validation_errors: Dict) -> List[Dict[str, str]]:
    """
    Format validation errors for response.
    
    Args:
        validation_errors: Dict of validation errors from validator
        
    Returns:
        List of formatted error objects
    """
    formatted_errors = []
    
    for section, errors in validation_errors.items():
        if isinstance(errors, list):
            for error in errors:
                formatted_errors.append({
                    'section': section,
                    'message': str(error)
                })
        elif isinstance(errors, dict):
            for field, field_errors in errors.items():
                if isinstance(field_errors, list):
                    for error in field_errors:
                        formatted_errors.append({
                            'section': f"{section}.{field}",
                            'message': str(error)
                        })
                else:
                    formatted_errors.append({
                        'section': f"{section}.{field}",
                        'message': str(field_errors)
                    })
    
    return formatted_errors

def validate_xbrl(data: Dict[str, Any]) -> Response:
    """
    Validate XBRL data and return a standardized response.
    
    Args:
        data: XBRL data to validate
        
    Returns:
        Standardized response object
    """
    from .validators import ACRAXBRLValidator
    
    try:
        # Validate the data
        validator = ACRAXBRLValidator(data)
        is_valid, errors = validator.validate()
        
        if is_valid:
            return success_response("XBRL data is valid according to ACRA rules")
        else:
            return error_response(
                message="XBRL validation failed",
                errors=errors
            )
    except Exception as e:
        logger.error(f"Error during XBRL validation: {str(e)}")
        return error_response(
            message=f"Error during XBRL validation: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )