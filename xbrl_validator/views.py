from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
import logging
from .validator_service import XBRLValidatorService
from .utils import error_response

logger = logging.getLogger(__name__)

@api_view(['POST'])
def validate_mapped_data(request):
    logger.debug(f"Received data: {request.data}")
    """
    Validate mapped XBRL data against ACRA rules.
    
    Takes XBRL data in request body and returns validation results.
    """
    try:
        # Parse request data
        if hasattr(request, 'data'):
            data = request.data
        else:
            data = json.loads(request.body.decode('utf-8'))
            
        # Initialize validator service
        validator_service = XBRLValidatorService()
        
        # Validate XBRL data
        is_valid, errors = validator_service.validate_xbrl_data(data)
        
        # Format response
        response_data = validator_service.format_validation_response(is_valid, errors)
        
        return Response(
            response_data,
            status=status.HTTP_200_OK if is_valid else status.HTTP_400_BAD_REQUEST
        )
        
    except json.JSONDecodeError:
        logger.warning("Invalid JSON data provided in request")
        return error_response(
            message="Invalid JSON data provided", 
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Unexpected error during validation: {str(e)}", exc_info=True)
        return error_response(
            message=f"An error occurred during validation: {str(e)}", 
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )