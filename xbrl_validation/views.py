from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
import logging
from .validator_service import XBRLValidatorService
from .utils import error_response, extract_mapped_data, sanitize_input, log_validation_result, success_response

logger = logging.getLogger(__name__)

@api_view(['POST'])
def validate_mapped_data(request):
    """
    Validate mapped XBRL data against ACRA rules.
    
    Takes XBRL data in request body and returns validation results.
    """
    try:
        # Extract data using the utility function
        data = extract_mapped_data(request)
        
        # Try to sanitize input data
        try:
            data = sanitize_input(data)
        except ValueError as e:
            return error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Initialize validator service
        validator_service = XBRLValidatorService()
        
        # Validate XBRL data
        is_valid, errors = validator_service.validate_xbrl_data(data)
        
        # Get taxonomy version from data
        taxonomy_version = "2022.2"  # Default
        if 'FilingInformation' in data:
            filing_info = data['FilingInformation']
            if 'TaxonomyVersion' in filing_info:
                taxonomy_version = filing_info['TaxonomyVersion']
                
        # Format response data
        result = {
            "is_valid": is_valid,
            "validation_timestamp": validator_service.get_current_timestamp(),
            "taxonomy_version": taxonomy_version
        }
        
        if not is_valid:
            result["validation_errors"] = errors
            
        # Log validation result
        log_validation_result(result)
        
        # Return appropriate response
        if is_valid:
            return success_response(
                data=result,
                message="XBRL data is valid according to ACRA rules"
            )
        else:
            return error_response(
                message="XBRL validation failed",
                errors=errors
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