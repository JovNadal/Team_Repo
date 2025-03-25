from rest_framework import viewsets, status, generics, filters
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json
from django_filters.rest_framework import DjangoFilterBackend
import asyncio
import logfire
import uuid
from threading import Thread

from .services.validators.mapping_validator import XBRLValidator
# Import the mapping agent and dependencies
from .services.agent import financial_statement_agent
from .services.dependencies import financial_deps
from .services.processors.mapping import XBRLFullProcessor, XBRLSimpleProcessor
from .services.processors.storage import map_pydantic_to_django_fields, store_mapped_data_to_db

from .utils.response import success_response, error_response
from .json_mapper import XBRLJSONMapper
from .models import (
    PartialXBRL, FilingInformation, StatementOfFinancialPosition,
    IncomeStatement, Notes, DirectorsStatement, AuditReport, CurrentAssets,
    NonCurrentAssets, CurrentLiabilities, NonCurrentLiabilities, Equity,
    TradeAndOtherReceivables, TradeAndOtherPayables, Revenue
)
from .serializers import (
    PartialXBRLSerializer, FilingInformationSerializer,
    StatementOfFinancialPositionSerializer, IncomeStatementSerializer,
    NotesSerializer, SimpleXBRLSerializer
)

logfire.configure(console=False, inspect_arguments=False)
logfire.instrument_openai()


# Field mapping for legacy field names
FIELD_MAPPING = {
    "WhetherTheFinancialStatementsArePreparedOnGoingConcernBasis": "is_going_concern",
    "WhetherThereAreAnyChangesToComparativeAmounts": "has_comparative_changes",
    "DescriptionOfPresentationCurrency": "presentation_currency",
    "DescriptionOfFunctionalCurrency": "functional_currency",
    "TypeOfXBRLFiling": "xbrl_filing_type",
    "TypeOfStatementOfFinancialPosition": "financial_position_type",
    "TypeOfAccountingStandardUsedToPrepareFinancialStatements": "accounting_standard",
    "NatureOfFinancialStatementsCompanyLevelOrConsolidated": "financial_statement_type",
    "DateOfAuthorisationForIssueOfFinancialStatements": "authorisation_date"
}

def normalize_filing_information(data):
    """Renames old field names to match Django model fields."""
    normalized_data = {}
    for key, value in data.items():
        new_key = FIELD_MAPPING.get(key, key)  # Replace if mapping exists, otherwise keep original
        normalized_data[new_key] = value
    return normalized_data

# Main XBRL API Views
class PartialXBRLListCreateView(generics.ListCreateAPIView):
    """
    API view to list all XBRL filings or create a new one
    """
    queryset = PartialXBRL.objects.all()
    serializer_class = PartialXBRLSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['filing_information__company_name', 'filing_information__unique_entity_number']
    search_fields = ['filing_information__company_name', 'filing_information__unique_entity_number']
    
    def create(self, request, *args, **kwargs):
        # Normalize field names if needed
        if "filing_information" in request.data:
            request.data["filing_information"] = normalize_filing_information(request.data["filing_information"])
        
        # Import necessary models
        from .models import (
            DirectorsStatement, AuditReport, CurrentAssets, NonCurrentAssets,
            CurrentLiabilities, NonCurrentLiabilities, Equity, TradeAndOtherReceivables,
            TradeAndOtherPayables
        )
        
        try:
            # Extract data from request
            filing_info_data = request.data.get('filing_information', {})
            directors_statement_data = request.data.get('directors_statement', {})
            audit_report_data = request.data.get('audit_report', {})
            
            # Extract statement of financial position data and its nested components
            sof_position_data = request.data.get('statement_of_financial_position', {})
            current_assets_data = sof_position_data.get('current_assets', {})
            noncurrent_assets_data = sof_position_data.get('noncurrent_assets', {})
            current_liabilities_data = sof_position_data.get('current_liabilities', {})
            noncurrent_liabilities_data = sof_position_data.get('noncurrent_liabilities', {})
            equity_data = sof_position_data.get('equity', {})
            
            # Extract income statement data
            income_statement_data = request.data.get('income_statement', {})
            
            # Extract notes data and its nested components
            notes_data = request.data.get('notes', {})
            trade_receivables_data = notes_data.get('trade_and_other_receivables', {})
            trade_payables_data = notes_data.get('trade_and_other_payables', {})
            
            # Convert receivables field names to payables field names if needed
            corrected_payables_data = {}
            if 'receivables_from_third_parties' in trade_payables_data:
                corrected_payables_data['payables_to_third_parties'] = trade_payables_data.get('receivables_from_third_parties')
            if 'receivables_from_related_parties' in trade_payables_data:
                corrected_payables_data['payables_to_related_parties'] = trade_payables_data.get('receivables_from_related_parties')
            if 'total_trade_and_other_receivables' in trade_payables_data:
                corrected_payables_data['total_trade_and_other_payables'] = trade_payables_data.get('total_trade_and_other_receivables')
            if 'unbilled_receivables' in trade_payables_data:
                corrected_payables_data['accrued_liabilities'] = trade_payables_data.get('unbilled_receivables')
            if 'other_receivables' in trade_payables_data:
                corrected_payables_data['other_payables'] = trade_payables_data.get('other_receivables')
            
            # Ensure total_trade_and_other_payables is set
            if 'total_trade_and_other_payables' not in corrected_payables_data:
                # If not provided, calculate from other fields or use a default value
                total = 0
                if 'payables_to_third_parties' in corrected_payables_data:
                    total += corrected_payables_data['payables_to_third_parties']
                if 'payables_to_related_parties' in corrected_payables_data:
                    total += corrected_payables_data['payables_to_related_parties']
                if 'accrued_liabilities' in corrected_payables_data:
                    total += corrected_payables_data['accrued_liabilities']
                if 'other_payables' in corrected_payables_data:
                    total += corrected_payables_data['other_payables']
                
                # If we have a calculated total, use it; otherwise, use the value from current_liabilities if available
                if total > 0:
                    corrected_payables_data['total_trade_and_other_payables'] = total
                elif 'trade_and_other_payables' in current_liabilities_data:
                    corrected_payables_data['total_trade_and_other_payables'] = current_liabilities_data.get('trade_and_other_payables')
                else:
                    # Fallback to a default value or the value from receivables
                    corrected_payables_data['total_trade_and_other_payables'] = trade_receivables_data.get('total_trade_and_other_receivables', 0)
            
            # Validate filing information data
            filing_info_serializer = FilingInformationSerializer(data=filing_info_data)
            filing_info_serializer.is_valid(raise_exception=True)
            
            # Create filing information first
            filing_info = filing_info_serializer.save()
            
            # Create directors statement
            directors_statement = DirectorsStatement.objects.create(
                filing=filing_info, 
                **directors_statement_data
            )
            
            # Create audit report
            audit_report = AuditReport.objects.create(
                filing=filing_info, 
                **audit_report_data
            )
            
            # Create financial position components
            current_assets = CurrentAssets.objects.create(
                filing=filing_info, 
                **current_assets_data
            )
            
            noncurrent_assets = NonCurrentAssets.objects.create(
                filing=filing_info, 
                **noncurrent_assets_data
            )
            
            current_liabilities = CurrentLiabilities.objects.create(
                filing=filing_info, 
                **current_liabilities_data
            )
            
            noncurrent_liabilities = NonCurrentLiabilities.objects.create(
                filing=filing_info, 
                **noncurrent_liabilities_data
            )
            
            equity = Equity.objects.create(
                filing=filing_info, 
                **equity_data
            )
            
            # Create statement of financial position
            sof_position = StatementOfFinancialPosition.objects.create(
                filing=filing_info,
                current_assets=current_assets,
                noncurrent_assets=noncurrent_assets,
                current_liabilities=current_liabilities,
                noncurrent_liabilities=noncurrent_liabilities,
                equity=equity,
                total_assets=sof_position_data.get('total_assets', 0),
                total_liabilities=sof_position_data.get('total_liabilities', 0)
            )
            
            # Create income statement
            income_statement = IncomeStatement.objects.create(
                filing=filing_info, 
                **income_statement_data
            )
            
            # Create notes components
            trade_receivables = TradeAndOtherReceivables.objects.create(
                filing=filing_info, 
                **trade_receivables_data
            )
            
            trade_payables = TradeAndOtherPayables.objects.create(
                filing=filing_info, 
                **corrected_payables_data
            )
            
            # Create notes
            notes = Notes.objects.create(
                filing=filing_info,
                trade_and_other_receivables=trade_receivables,
                trade_and_other_payables=trade_payables
            )
            
            # Finally create the partial XBRL object
            xbrl = PartialXBRL.objects.create(
                filing_information=filing_info,
                directors_statement=directors_statement,
                audit_report=audit_report,
                statement_of_financial_position=sof_position,
                income_statement=income_statement,
                notes=notes
            )
            
            # Return the response with the created instance
            serializer = self.get_serializer(xbrl)
            headers = self.get_success_headers(serializer.data)
            
            # Add success message to response
            response_data = {
                "success": True,
                "message": "XBRL filing created successfully",
                "data": serializer.data
            }
            
            return success_response(
                message="XBRL filing created successfully",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            return error_response(
                message="Failed to create XBRL filing",
                error=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    def perform_create(self, serializer):
        # Override to handle the case where we're skipping validation
        if not hasattr(serializer, '_validated_data'):
            serializer._validated_data = serializer.initial_data
        serializer.save()
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            return success_response(
                message="XBRL filings retrieved successfully",
                data={
                    "count": paginated_response.data['count'],
                    "data": paginated_response.data['results']
                }
            )
            
        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            message="XBRL filings retrieved successfully",
            data=serializer.data
        )

class PartialXBRLDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update or delete a specific XBRL filing
    """
    queryset = PartialXBRL.objects.all()
    serializer_class = PartialXBRLSerializer
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(
            message="XBRL filing retrieved successfully",
            data=serializer.data
        )
    
    def update(self, request, *args, **kwargs):
        # Normalize field names if needed
        if "filing_information" in request.data:
            request.data["filing_information"] = normalize_filing_information(request.data["filing_information"])
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return success_response(
            message="XBRL filing updated successfully",
            data=serializer.data
        )
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        uen = instance.filing_information.unique_entity_number
        self.perform_destroy(instance)
        return success_response(
            message=f"XBRL filing with UEN {uen} deleted successfully",
            status_code=status.HTTP_200_OK
        )

class SimpleXBRLView(generics.CreateAPIView):
    """Submit simplified XBRL data"""
    serializer_class = SimpleXBRLSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        validator = XBRLValidator()
        validation_result = validator.validate(serializer.validated_data)

        if not validation_result.is_valid:
            return error_response(
                message="Financial data validation failed",
                error=validation_result.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        processor = XBRLSimpleProcessor()
        task_id = processor.process_async(serializer.validated_data)

        return success_response(
            message="Request processed successfully",
            data={"task_id": task_id},
            status_code=status.HTTP_202_ACCEPTED
        )

# Search and Utility Views
class XBRLSearchView(generics.ListAPIView):
    """
    API view to search XBRL filings
    """
    queryset = PartialXBRL.objects.all()
    serializer_class = PartialXBRLSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        'filing_information__company_name', 
        'filing_information__unique_entity_number',
        'filing_information__xbrl_filing_type',
        'filing_information__financial_statement_type',
        'filing_information__accounting_standard',
    ]
    search_fields = [
        'filing_information__company_name',
        'filing_information__unique_entity_number',
    ]
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            return success_response(
                message="Search results retrieved successfully",
                data={
                    "count": paginated_response.data['count'],
                    "next": paginated_response.data['next'],
                    "previous": paginated_response.data['previous'],
                    "data": paginated_response.data['results']
                }
            )
            
        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            message="Search results retrieved successfully",
            data={
                "count": len(serializer.data),
                "data": serializer.data
            }
        )


@api_view(['PUT'])
def update_mapped_data(request, id):
    """
    Update an existing financial statement mapping in the database using UUID
    """
    try:
        logfire.info(f"Starting financial data manual update for ID: {id}")
        
        # Check if the XBRL filing exists using UUID
        try:
            xbrl = PartialXBRL.objects.get(id=id)
            # Store the UEN for later use in responses
            uen = xbrl.filing_information.unique_entity_number
        except PartialXBRL.DoesNotExist:
            return error_response(
                message=f"No XBRL filing found with ID: {id}",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Extract mapped data directly from request - assuming user has already mapped it
        mapped_data = request.data.get('mapped_data', {})
        
        if not mapped_data:
            return error_response(
                message="Missing mapped_data in request",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        logfire.debug("Manual update data received", data_size=len(json.dumps(mapped_data)))
        
        # Process the manually mapped data to ensure it's in Django format
        try:
            # If data is still in PascalCase, convert it to snake_case
            if any(key for key in mapped_data.keys() if key[0].isupper()):
                mapped_data = map_pydantic_to_django_fields(mapped_data)
            
            if 'filing_information' not in mapped_data:
                mapped_data['filing_information'] = {}
            
            # Preserve the UEN to ensure we're updating the same record
            mapped_data['filing_information']['unique_entity_number'] = uen
            
            # Validate that no ID fields are being modified - this is a security measure
            forbidden_fields = []
            
            # Check filing_information
            if 'filing_information' in mapped_data:
                filing_info = xbrl.filing_information
                for field in mapped_data['filing_information']:
                    if field == 'id' or field.endswith('_id'):
                        # Only add to forbidden fields if the value is actually changing
                        current_value = getattr(filing_info, field, None)
                        new_value = mapped_data['filing_information'][field]
                        if str(current_value) != str(new_value):
                            forbidden_fields.append(f"filing_information.{field}")
            
            # Check other top-level sections
            for section in ['directors_statement', 'audit_report', 'statement_of_financial_position', 
                           'income_statement', 'notes']:
                if section in mapped_data:
                    # Get the current section object
                    section_obj = getattr(xbrl, section, None)
                    if not section_obj:
                        continue
                        
                    # Check for ID fields at section level
                    for field in mapped_data[section]:
                        if field == 'id' or field == 'filing' or field.endswith('_id'):
                            # Only add to forbidden fields if the value is actually changing
                            current_value = getattr(section_obj, field, None)
                            new_value = mapped_data[section][field]
                            if str(current_value) != str(new_value):
                                forbidden_fields.append(f"{section}.{field}")
                    
                    # Check nested components in statement_of_financial_position
                    if section == 'statement_of_financial_position':
                        for component in ['current_assets', 'noncurrent_assets', 'current_liabilities', 
                                         'noncurrent_liabilities', 'equity']:
                            if component in mapped_data[section]:
                                component_obj = getattr(section_obj, component, None)
                                if not component_obj:
                                    continue
                                
                                for field in mapped_data[section][component]:
                                    if field == 'id' or field == 'filing' or field.endswith('_id'):
                                        # Only add to forbidden fields if the value is actually changing
                                        current_value = getattr(component_obj, field, None)
                                        new_value = mapped_data[section][component][field]
                                        if str(current_value) != str(new_value):
                                            forbidden_fields.append(f"{section}.{component}.{field}")
                    
                    # Check nested components in notes
                    if section == 'notes':
                        for component in ['trade_and_other_receivables', 'trade_and_other_payables', 'revenue']:
                            if component in mapped_data[section]:
                                component_obj = getattr(section_obj, component, None)
                                if not component_obj:
                                    continue
                                    
                                for field in mapped_data[section][component]:
                                    if field == 'id' or field == 'filing' or field.endswith('_id'):
                                        # Only add to forbidden fields if the value is actually changing
                                        current_value = getattr(component_obj, field, None)
                                        new_value = mapped_data[section][component][field]
                                        if str(current_value) != str(new_value):
                                            forbidden_fields.append(f"{section}.{component}.{field}")
            
            # If any forbidden fields were found, return an error
            if forbidden_fields:
                return error_response(
                    message="Modification of ID or relationship fields is not allowed",
                    error=f"The following fields cannot be modified: {', '.join(forbidden_fields)}",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Handle the transaction to avoid constraint violations
            with transaction.atomic():
                # Store old ID for reference
                old_id = xbrl.id
                
                # Get filing information ID before updating
                filing_info_id = xbrl.filing_information.id
                
                # Instead of deleting and recreating, update the existing models
                # First, update filing information
                filing_info_data = mapped_data.get('filing_information', {})
                filing_info = FilingInformation.objects.get(id=filing_info_id)
                
                # Update filing info fields - FORBID id and _id fields
                for field, value in filing_info_data.items():
                    if (hasattr(filing_info, field) and 
                        field != 'id' and 
                        not field.endswith('_id')):
                        setattr(filing_info, field, value)
                filing_info.save()
                
                # Update directors statement
                if 'directors_statement' in mapped_data and xbrl.directors_statement:
                    dirs_stmt_data = mapped_data.get('directors_statement', {})
                    dirs_stmt = xbrl.directors_statement
                    for field, value in dirs_stmt_data.items():
                        # FORBID id, filing and _id fields
                        if (hasattr(dirs_stmt, field) and 
                            field != 'filing' and 
                            field != 'id' and 
                            not field.endswith('_id')):
                            setattr(dirs_stmt, field, value)
                    dirs_stmt.save()
                
                # Update audit report
                if 'audit_report' in mapped_data and xbrl.audit_report:
                    audit_data = mapped_data.get('audit_report', {})
                    audit = xbrl.audit_report
                    for field, value in audit_data.items():
                        # FORBID id, filing and _id fields
                        if (hasattr(audit, field) and 
                            field != 'filing' and 
                            field != 'id' and 
                            not field.endswith('_id')):
                            setattr(audit, field, value)
                    audit.save()
                
                # Update financial position data
                if 'statement_of_financial_position' in mapped_data and xbrl.statement_of_financial_position:
                    position_data = mapped_data.get('statement_of_financial_position', {})
                    position = xbrl.statement_of_financial_position
                    
                    # Update top-level fields (confirm these aren't ID fields)
                    for field in ['total_assets', 'total_liabilities']:
                        if field in position_data and not field.endswith('_id'):
                            setattr(position, field, position_data[field])
                    
                    # Update nested components
                    for component in ['current_assets', 'noncurrent_assets', 'current_liabilities', 
                                     'noncurrent_liabilities', 'equity']:
                        if component in position_data and hasattr(position, component):
                            component_obj = getattr(position, component)
                            component_data = position_data[component]
                            for field, value in component_data.items():
                                # FORBID id, filing and _id fields
                                if (hasattr(component_obj, field) and 
                                    field != 'filing' and 
                                    field != 'id' and 
                                    not field.endswith('_id')):
                                    setattr(component_obj, field, value)
                            component_obj.save()
                    
                    position.save()
                
                # Update income statement
                if 'income_statement' in mapped_data and xbrl.income_statement:
                    income_data = mapped_data.get('income_statement', {})
                    income = xbrl.income_statement
                    for field, value in income_data.items():
                        # FORBID id, filing and _id fields
                        if (hasattr(income, field) and 
                            field != 'filing' and 
                            field != 'id' and 
                            not field.endswith('_id')):
                            setattr(income, field, value)
                    income.save()
                
                # Update notes
                if 'notes' in mapped_data and xbrl.notes:
                    notes_data = mapped_data.get('notes', {})
                    notes = xbrl.notes
                    
                    # Update trade_and_other_receivables
                    if 'trade_and_other_receivables' in notes_data and notes.trade_and_other_receivables:
                        receivables_data = notes_data['trade_and_other_receivables']
                        receivables = notes.trade_and_other_receivables
                        for field, value in receivables_data.items():
                            # FORBID id, filing and _id fields
                            if (hasattr(receivables, field) and 
                                field != 'filing' and 
                                field != 'id' and 
                                not field.endswith('_id')):
                                setattr(receivables, field, value)
                        receivables.save()
                    
                    # Update trade_and_other_payables
                    if 'trade_and_other_payables' in notes_data and notes.trade_and_other_payables:
                        payables_data = notes_data['trade_and_other_payables']
                        payables = notes.trade_and_other_payables
                        for field, value in payables_data.items():
                            # FORBID id, filing and _id fields
                            if (hasattr(payables, field) and 
                                field != 'filing' and 
                                field != 'id' and 
                                not field.endswith('_id')):
                                setattr(payables, field, value)
                        payables.save()
                    
                    # Update revenue data if it exists
                    if 'revenue' in notes_data and hasattr(notes, 'revenue') and notes.revenue:
                        revenue_data = notes_data['revenue']
                        revenue = notes.revenue
                        for field, value in revenue_data.items():
                            # FORBID id, filing and _id fields
                            if (hasattr(revenue, field) and 
                                field != 'filing' and 
                                field != 'id' and 
                                not field.endswith('_id')):
                                setattr(revenue, field, value)
                        revenue.save()
                
                logfire.info(f"Successfully updated financial data in database. ID: {xbrl.id}")
                
                # Return success response
                return success_response(
                    message=f"Financial data for UEN {uen} updated successfully",
                    data={
                        "filing_id": str(xbrl.id),
                        "mapped_data": mapped_data
                    }
                )
        except Exception as db_error:
            logfire.exception("Error updating financial data in database", error=str(db_error))
            # Return the mapped data even if update failed
            return error_response(
                message=f"Financial data could not be updated in the database for ID: {id}",
                error=str(db_error),
                data={"mapped_data": mapped_data},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        # Enhanced error logging with more details
        error_type = type(e).__name__
        error_details = str(e)
        
        logfire.exception(
            f"Error during financial data update for ID: {id}", 
            error=error_details,
            error_type=error_type
        )
        
        # Return error response
        return error_response(
            message=f"Failed to update financial data for ID: {id}",
            error=error_details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def map_financial_data(request):
    """
    Map financial statement data to standard format and store in database.
    
    Uses Fast Response Pattern:
    1. Validates request data
    2. Returns immediate response with task ID
    3. Processes data asynchronously in background
    """
    try:
        logfire.info("Starting financial data mapping request")
        
        # Extract data from request
        data = request.data.get('data', {})
        
        if not data:
            return error_response(
                message="No financial data provided for mapping",
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        # Generate a task ID for tracking
        task_id = str(uuid.uuid4())
        
        # Basic validation can be done before response
        validator = XBRLValidator()
        validation_result = validator.validate(data)
        
        if not validation_result.is_valid:
            logfire.warning(f"Validation failed for financial data", task_id=task_id)
            return error_response(
                message="Financial data validation failed",
                error=validation_result.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Send immediate response with task ID
        logfire.info(f"Sending immediate response with task_id: {task_id}")
        response = success_response(
            message="Financial data mapping request accepted for processing",
            data={
                "status": "processing",
                "task_id": task_id
            },
            status_code=status.HTTP_202_ACCEPTED
        )
        
        # Start background processing thread
        Thread(
            target=process_xbrl_data_after_response,
            args=(data, task_id),
            daemon=True
        ).start()
        return response
            
    except Exception as e:
        # Error handling for request acceptance phase
        error_type = type(e).__name__
        error_details = str(e)
        
        logfire.exception(
            "Error accepting financial data mapping request", 
            error=error_details,
            error_type=error_type
        )
        
        return error_response(
            message="Failed to accept financial data mapping request",
            error=error_details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def process_xbrl_data_after_response(data, task_id):
    """
    Process XBRL data after response has been sent.
    
    Args:
        data (dict): The financial data to process
        task_id (str): The task identifier for tracking
    """
    # Import here to avoid potential circular imports
    from django.db import close_old_connections
    from django.db import connection
    
    try:
        # Close any DB connections from the request cycle
        close_old_connections()
        
        logfire.info(f"Background processing started for task_id: {task_id}")
        
        # Use the service layer processor
        processor = XBRLSimpleProcessor()
        
        # Process the data - this will handle mapping and storage
        result = processor.process_sync(data)
        
        # Store the result with the task ID for later retrieval if needed
        # This could be in Redis, database, or another store
        # For now, just log the result
        logfire.info(f"Financial data mapping completed for task_id: {task_id}",
                    success=result.get('success', False),
                    filing_id=result.get('filing_id', None))
        
    except Exception as e:
        # Error handling for background processing
        error_type = type(e).__name__
        error_details = str(e)
        
        logfire.exception(
            f"Error during background processing for task_id: {task_id}", 
            error=error_details,
            error_type=error_type
        )
    finally:
        # Always close connections when thread is done
        close_old_connections()
        if connection.connection:
            connection.close()
