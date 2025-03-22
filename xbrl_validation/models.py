from django.db import models
import uuid
from xbrl_mapping.models import PartialXBRL

class ValidationSeverity(models.TextChoices):
    """Validation severity levels"""
    ERROR = "Error", "Error"
    WARNING = "Warning", "Warning"
    INFO = "Info", "Info"

class ValidationCategory(models.TextChoices):
    """Validation error categories"""
    STRUCTURE = "Structure", "Structure"
    CALCULATION = "Calculation", "Calculation"
    CONSISTENCY = "Consistency", "Consistency"
    BUSINESS_RULE = "Business Rule", "Business Rule"
    ACRA_RULE = "ACRA Rule", "ACRA Rule"

class ValidationResult(models.Model):
    """Store results of XBRL validation"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    xbrl_document = models.ForeignKey(PartialXBRL, on_delete=models.CASCADE, related_name='validation_results')
    validation_date = models.DateTimeField(auto_now_add=True)
    is_valid = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Validation of {self.xbrl_document.filing_information.company_name} ({self.validation_date})"

class ValidationError(models.Model):
    """Individual validation errors"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    validation_result = models.ForeignKey(ValidationResult, on_delete=models.CASCADE, related_name='errors')
    section = models.CharField(max_length=100, help_text="Section of the XBRL document where the error occurred")
    message = models.TextField(help_text="Error message")
    severity = models.CharField(max_length=10, choices=ValidationSeverity.choices, default=ValidationSeverity.ERROR)
    category = models.CharField(max_length=20, choices=ValidationCategory.choices, default=ValidationCategory.BUSINESS_RULE)
    
    def __str__(self):
        return f"{self.section}: {self.message}"