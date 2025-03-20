from typing import Dict, List, Tuple, Any
import logging
from .validators import ACRAXBRLValidator
from .utils import format_validation_errors

logger = logging.getLogger(__name__)

class XBRLValidatorService:
    """Service layer for XBRL validation operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def validate_xbrl_data(self, data: Dict[str, Any]) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Validate XBRL data against ACRA rules
        
        Args:
            data: XBRL data to validate
            
        Returns:
            Tuple containing:
            - Boolean indicating if validation passed
            - Dictionary of validation errors by section
        """
        try:
            # Create validator instance
            validator = ACRAXBRLValidator(data)
            
            # Run validation
            is_valid, errors = validator.validate()
            
            if not is_valid:
                self.logger.warning(f"XBRL validation failed with {len(errors)} errors")
                
            return is_valid, errors
            
        except Exception as e:
            self.logger.error(f"Error during XBRL validation: {str(e)}", exc_info=True)
            raise
            
    def format_validation_response(self, is_valid: bool, errors: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Format validation results into a standardized response
        
        Args:
            is_valid: Whether validation passed
            errors: Dictionary of validation errors
            
        Returns:
            Formatted response dictionary
        """
        if is_valid:
            return {
                'success': True,
                'message': 'XBRL data is valid according to ACRA rules'
            }
        else:
            formatted_errors = format_validation_errors(errors)
            return {
                'success': False,
                'message': 'XBRL validation failed',
                'error_count': len(formatted_errors),
                'errors': formatted_errors
            } 