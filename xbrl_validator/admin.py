from django.contrib import admin
from .models import ValidationResult, ValidationError

@admin.register(ValidationResult)
class ValidationResultAdmin(admin.ModelAdmin):
    list_display = ('xbrl_document', 'validation_date', 'is_valid')
    list_filter = ('is_valid', 'validation_date')
    search_fields = ('xbrl_document__filing_information__company_name',)

@admin.register(ValidationError)
class ValidationErrorAdmin(admin.ModelAdmin):
    list_display = ('section', 'message', 'severity', 'category')
    list_filter = ('severity', 'category', 'section')
    search_fields = ('message',)