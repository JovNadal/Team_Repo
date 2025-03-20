from rest_framework import serializers
from xbrl_mapping.models import PartialXBRL
from .validators import ACRAXBRLValidator

class XBRLValidationSerializer(serializers.Serializer):
    """
    Serializer for validating XBRL data against ACRA rules.
    
    This serializer doesn't persist data but performs validation 
    against the ACRA XBRL taxonomy and business rules.
    """
    data = serializers.JSONField(required=True)
    
    def validate_data(self, value):
        """
        Validate the XBRL data structure is complete and well-formed.
        """
        required_sections = ['filing_information', 'statement_of_financial_position', 'income_statement']
        
        for section in required_sections:
            if section not in value:
                raise serializers.ValidationError(f"Missing required section: {section}")
                
        # Additional structural validation could be added here
        return value
    
    def validate(self, attrs):
        """
        Perform ACRA-specific validation on the XBRL data.
        """
        data = attrs.get('data')
        
        # Perform ACRA-specific validation
        validator = ACRAXBRLValidator(data)
        is_valid, validation_errors = validator.validate()
        
        if not is_valid:
            # Format errors to match DRF's expected error structure
            formatted_errors = {}
            for section, errors in validation_errors.items():
                formatted_errors[section] = errors
                
            raise serializers.ValidationError(formatted_errors)
            
        return attrs