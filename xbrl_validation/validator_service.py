from typing import Dict, List, Tuple, Any, Union
import logging
from .validators import ACRAXBRLValidator
from .utils import format_validation_errors
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)

class XBRLValidatorService:
    """
    Service for validating XBRL data against ACRA rules.
    """
    
    def __init__(self):
        """Initialize the validator service"""
        pass
    
    def validate_xbrl_data(self, data: Dict[str, Any]) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Validate XBRL data against ACRA rules
        
        Args:
            data: Dictionary containing XBRL data (already extracted and sanitized)
            
        Returns:
            Tuple containing:
            - Boolean indicating if validation passed
            - Dictionary of errors by section
        """
        try:
            # Use the ACRA validator directly on the provided data
            # The data should already be extracted and sanitized by the caller
            validator = ACRAXBRLValidator(data)
            is_valid, errors = validator.validate()
            
            return is_valid, errors
            
        except TypeError as e:
            # Handle specific TypeError which might be from None values
            error_str = str(e)
            detailed_error = f"Type error during validation: {error_str}"
            logger.error(detailed_error, exc_info=True)
            
            # Provide a more helpful error message depending on the error
            if "'NoneType' object" in error_str:
                return False, {'general': [
                    "A required field contains a null (None) value. Please check Trade and Other Payables fields and ensure they have numeric values instead of null."
                ]}
            
            return False, {'general': [detailed_error]}
            
        except AttributeError as e:
            # Handle specific AttributeError which might be from accessing attributes on None
            error_str = str(e)
            detailed_error = f"Attribute error during validation: {error_str}"
            logger.error(detailed_error, exc_info=True)
            
            # Provide a more helpful error message depending on the error
            if "'NoneType' object has no attribute" in error_str:
                return False, {'general': [
                    "A null value was found where an object was expected. Please check your data structure and ensure all required fields are properly populated."
                ]}
            
            return False, {'general': [detailed_error]}
            
        except Exception as e:
            # Get detailed error information including traceback
            error_str = str(e)
            tb = traceback.format_exc()
            logger.error(f"Error in validation service: {error_str}\n{tb}")
            
            # Provide a user-friendly error message
            return False, {'general': [f"An error occurred during validation: {error_str}"]}
    
    def format_validation_response(self, is_valid: bool, errors: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Format validation results into a structured response
        
        Args:
            is_valid: Boolean indicating if validation passed
            errors: Dictionary of errors by section
            
        Returns:
            Dictionary with formatted response
        """
        response = {
            "status": "success" if is_valid else "error",
            "is_valid": is_valid,
            "validation_timestamp": self.get_current_timestamp()
        }
        
        if not is_valid:
            response["validation_errors"] = errors
            
        return response
    
    def get_current_timestamp(self) -> str:
        """
        Get current timestamp in ISO format
        
        Returns:
            String with current timestamp
        """
        return datetime.now().isoformat()
    
    def get_taxonomy_version(self, data: Dict[str, Any]) -> str:
        """
        Get the taxonomy version from the data
        
        Args:
            data: Dictionary containing XBRL data
            
        Returns:
            String with taxonomy version
        """
        # Try to find taxonomy version in filing information
        if 'FilingInformation' in data:
            filing_info = data['FilingInformation']
            if 'TaxonomyVersion' in filing_info:
                version = filing_info['TaxonomyVersion']
                # Only return valid 2022 versions
                if version in {'2022', '2022.2'}:
                    return version
                    
        # Default to latest version
        return "2022.2" 