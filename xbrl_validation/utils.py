from rest_framework.response import Response
from rest_framework import status
from typing import Dict, List, Any, Optional, Union
import json
import logging
from .serializers import XBRLValidationSerializer
from datetime import datetime

logger = logging.getLogger(__name__)

def extract_mapped_data(request):
    """Extract mapped data from request object or body"""
    if hasattr(request, 'data'):
        data = request.data
    else:
        data = json.loads(request.body.decode('utf-8'))
        
    # Extract mapped_data if present in different possible structures
    if 'mapped_data' in data:
        return data['mapped_data']
    elif 'data' in data and isinstance(data['data'], dict) and 'mapped_data' in data['data']:
        return data['data']['mapped_data']
        
    return data

def sanitize_input(data):
    """Sanitize and validate input data"""
    if not data:
        raise ValueError("Empty data provided")
    
    # Check if required sections exist
    required_sections = ['FilingInformation', 'StatementOfFinancialPosition', 'IncomeStatement']
    missing_sections = []
    
    for section in required_sections:
        if section not in data:
            missing_sections.append(section)
            
    if missing_sections:
        raise ValueError(f"Missing required section(s): {', '.join(missing_sections)}")
    
    # Check for null values in trade payables fields
    if 'StatementOfFinancialPosition' in data:
        sfp = data['StatementOfFinancialPosition']
        
        if 'CurrentLiabilities' in sfp and 'TradeAndOtherPayablesCurrent' in sfp['CurrentLiabilities'] and sfp['CurrentLiabilities']['TradeAndOtherPayablesCurrent'] is None:
            # Convert None to 0 for TradeAndOtherPayablesCurrent
            sfp['CurrentLiabilities']['TradeAndOtherPayablesCurrent'] = 0
            
        if 'NonCurrentLiabilities' in sfp and 'TradeAndOtherPayablesNoncurrent' in sfp['NonCurrentLiabilities'] and sfp['NonCurrentLiabilities']['TradeAndOtherPayablesNoncurrent'] is None:
            # Convert None to 0 for TradeAndOtherPayablesNoncurrent
            sfp['NonCurrentLiabilities']['TradeAndOtherPayablesNoncurrent'] = 0
    
    return data

def log_validation_result(result):
    """Log validation result with appropriate level"""
    if result["is_valid"]:
        logger.info(f"Validation succeeded for submission with taxonomy {result.get('taxonomy_version')}")
    else:
        error_count = len(result.get("validation_errors", {}))
        logger.warning(f"Validation failed with {error_count} errors")

def success_response(data=None, message=None, status_code=status.HTTP_200_OK):
    """Generate a standardized success response"""
    response_data = {
        "status": "success",
    }
    
    if message:
        response_data["message"] = message
    
    if data:
        response_data["data"] = data
    
    return Response(response_data, status=status_code)

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
        'status': 'error',
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
        # Extract the actual data to validate from potential nested structures
        data_to_validate = data
        
        # Check if data is in a nested structure
        if isinstance(data, dict):
            # Case 1: Data is in 'mapped_data' directly
            if 'mapped_data' in data:
                data_to_validate = data['mapped_data']
            # Case 2: Data is in 'data.mapped_data'
            elif 'data' in data and isinstance(data['data'], dict) and 'mapped_data' in data['data']:
                data_to_validate = data['data']['mapped_data']
        
        # Sanitize input data
        try:
            data_to_validate = sanitize_input(data_to_validate)
        except ValueError as e:
            return error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate the data
        validator = ACRAXBRLValidator(data_to_validate)
        is_valid, errors = validator.validate()
        
        result = {
            "is_valid": is_valid,
            "validation_timestamp": datetime.now().isoformat(),
            "taxonomy_version": data_to_validate.get('FilingInformation', {}).get('TaxonomyVersion', "2022.2")
        }
        
        if not is_valid:
            result["validation_errors"] = errors
        
        # Log the validation result
        log_validation_result(result)
        
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
    except TypeError as e:
        error_str = str(e)
        logger.error(f"Type error during XBRL validation: {error_str}", exc_info=True)
        
        if "'NoneType' object" in error_str:
            return error_response(
                message="Validation error: Null value found where a value is required",
                errors={'general': [f"A required field contains a null (None) value. Please check Trade and Other Payables fields and ensure they have numeric values instead of null."]},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        return error_response(
            message=f"Type error during XBRL validation: {error_str}",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error during XBRL validation: {str(e)}", exc_info=True)
        return error_response(
            message=f"Error during XBRL validation: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )