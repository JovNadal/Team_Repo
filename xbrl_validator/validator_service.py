from typing import Dict, List, Tuple, Any, Union
import logging
from .validators import ACRAXBRLValidator
from .utils import format_validation_errors
from datetime import datetime

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
            data: Dictionary containing XBRL data
            
        Returns:
            Tuple containing:
            - Boolean indicating if validation passed
            - Dictionary of errors by section
        """
        try:
            # Use the ACRA validator
            validator = ACRAXBRLValidator(data)
            is_valid, errors = validator.validate()
            
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"Error in validation service: {str(e)}", exc_info=True)
            return False, {'general': [f"An error occurred during validation: {str(e)}"]}
    
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
            "validation_status": "success" if is_valid else "error",
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
        filing_info = None
        for key in ['FilingInformation', 'filing_information']:
            if key in data:
                filing_info = data[key]
                break
                
        if filing_info:
            for key in ['TaxonomyVersion', 'taxonomy_version']:
                if key in filing_info:
                    return filing_info[key]
                    
        # Default to latest version
        return "2022.2" 