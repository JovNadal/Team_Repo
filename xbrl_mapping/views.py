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

logfire.configure(console=False, inspect_arguments=False)
logfire.instrument_openai()

# Import the mapping agent and dependencies
from .services.agent import financial_statement_agent
from .services.dependencies import financial_deps

from .utils import success_response, error_response

from .models import (
    PartialXBRL, FilingInformation, StatementOfFinancialPosition,
    IncomeStatement, Notes, DirectorsStatement, AuditReport, CurrentAssets,
    NonCurrentAssets, CurrentLiabilities, NonCurrentLiabilities, Equity,
    TradeAndOtherReceivables, TradeAndOtherPayables, Revenue
)
from .serializers import (
    PartialXBRLSerializer, FilingInformationSerializer,
    StatementOfFinancialPositionSerializer, IncomeStatementSerializer,
    NotesSerializer
)
from .json_mapper import XBRLJSONMapper

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

def prepare_nested_data_for_validation(data):
    """
    Prepares nested data for validation by adding temporary filing field values.
    This allows the serializer validation to pass, and the actual filing relationships
    will be properly set during the create method.
    """
    if not data:
        return data
        
    # Create a deep copy to avoid modifying the original data
    prepared_data = json.loads(json.dumps(data))
    
    # Add temporary filing field to all nested objects that require it
    for section in ['directors_statement', 'audit_report', 'statement_of_financial_position', 
                   'income_statement', 'notes']:
        if section in prepared_data:
            if 'filing' not in prepared_data[section]:
                prepared_data[section]['filing'] = None
                
            # Handle nested sections within statement_of_financial_position
            if section == 'statement_of_financial_position':
                for subsection in ['current_assets', 'noncurrent_assets', 'current_liabilities', 
                                  'noncurrent_liabilities', 'equity']:
                    if subsection in prepared_data[section]:
                        if 'filing' not in prepared_data[section][subsection]:
                            prepared_data[section][subsection]['filing'] = None
            
            # Handle nested sections within notes
            if section == 'notes':
                for subsection in ['trade_and_other_receivables', 'trade_and_other_payables']:
                    if subsection in prepared_data[section]:
                        if 'filing' not in prepared_data[section][subsection]:
                            prepared_data[section][subsection]['filing'] = None
    
    return prepared_data

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
            
            return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)
            
        except Exception as e:
            return Response({
                "success": False,
                "message": "Failed to create XBRL filing",
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
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
            return Response({
                "success": True,
                "message": "XBRL filings retrieved successfully",
                "count": paginated_response.data['count'],
                "next": paginated_response.data['next'],
                "previous": paginated_response.data['previous'],
                "data": paginated_response.data['results']
            })
            
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "XBRL filings retrieved successfully",
            "count": len(serializer.data),
            "data": serializer.data
        })

class PartialXBRLDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update or delete a specific XBRL filing
    """
    queryset = PartialXBRL.objects.all()
    serializer_class = PartialXBRLSerializer
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "message": "XBRL filing retrieved successfully",
            "data": serializer.data
        })
    
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

        return Response({
            "success": True,
            "message": "XBRL filing updated successfully",
            "data": serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        uen = instance.filing_information.unique_entity_number
        self.perform_destroy(instance)
        return Response({
            "success": True,
            "message": f"XBRL filing with UEN {uen} deleted successfully"
        }, status=status.HTTP_200_OK)

# FilingInformation views
class FilingInformationListView(generics.ListAPIView):
    """
    API view to list all filing information
    """
    queryset = FilingInformation.objects.all()
    serializer_class = FilingInformationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['company_name', 'unique_entity_number', 'xbrl_filing_type']
    search_fields = ['company_name', 'unique_entity_number']
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            return Response({
                "success": True,
                "message": "Filing information retrieved successfully",
                "count": paginated_response.data['count'],
                "next": paginated_response.data['next'],
                "previous": paginated_response.data['previous'],
                "data": paginated_response.data['results']
            })
            
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "Filing information retrieved successfully",
            "count": len(serializer.data),
            "data": serializer.data
        })

class FilingInformationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update or delete filing information
    """
    queryset = FilingInformation.objects.all()
    serializer_class = FilingInformationSerializer
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "message": "Filing information retrieved successfully",
            "data": serializer.data
        })
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response({
            "success": True,
            "message": "Filing information updated successfully",
            "data": serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        uen = instance.unique_entity_number
        self.perform_destroy(instance)
        return Response({
            "success": True,
            "message": f"Filing information with UEN {uen} deleted successfully"
        }, status=status.HTTP_200_OK)

# Financial Statement Component Views
class StatementOfFinancialPositionListView(generics.ListAPIView):
    """
    API view to list all statements of financial position
    """
    queryset = StatementOfFinancialPosition.objects.all()
    serializer_class = StatementOfFinancialPositionSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            return Response({
                "success": True,
                "message": "Financial position statements retrieved successfully",
                "count": paginated_response.data['count'],
                "next": paginated_response.data['next'],
                "previous": paginated_response.data['previous'],
                "data": paginated_response.data['results']
            })
            
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "Financial position statements retrieved successfully",
            "count": len(serializer.data),
            "data": serializer.data
        })

class StatementOfFinancialPositionDetailView(generics.RetrieveUpdateAPIView):
    """
    API view to retrieve or update a statement of financial position
    """
    serializer_class = StatementOfFinancialPositionSerializer
    
    def get_queryset(self):
        return StatementOfFinancialPosition.objects.filter(filing_id=self.kwargs['filing_id'])
    
    def get_object(self):
        queryset = self.get_queryset()
        return queryset.first()
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "message": "Financial position statement retrieved successfully",
            "data": serializer.data
        })
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response({
            "success": True,
            "message": "Financial position statement updated successfully",
            "data": serializer.data
        })

class IncomeStatementListView(generics.ListAPIView):
    """
    API view to list all income statements
    """
    queryset = IncomeStatement.objects.all()
    serializer_class = IncomeStatementSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            return Response({
                "success": True,
                "message": "Income statements retrieved successfully",
                "count": paginated_response.data['count'],
                "next": paginated_response.data['next'],
                "previous": paginated_response.data['previous'],
                "data": paginated_response.data['results']
            })
            
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "Income statements retrieved successfully",
            "count": len(serializer.data),
            "data": serializer.data
        })

class IncomeStatementDetailView(generics.RetrieveUpdateAPIView):
    """
    API view to retrieve or update an income statement
    """
    serializer_class = IncomeStatementSerializer
    
    def get_queryset(self):
        return IncomeStatement.objects.filter(filing_id=self.kwargs['filing_id'])
    
    def get_object(self):
        queryset = self.get_queryset()
        return queryset.first()
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "message": "Income statement retrieved successfully",
            "data": serializer.data
        })
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response({
            "success": True,
            "message": "Income statement updated successfully",
            "data": serializer.data
        })

class NotesListView(generics.ListAPIView):
    """
    API view to list all notes
    """
    queryset = Notes.objects.all()
    serializer_class = NotesSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            return Response({
                "success": True,
                "message": "Notes retrieved successfully",
                "count": paginated_response.data['count'],
                "next": paginated_response.data['next'],
                "previous": paginated_response.data['previous'],
                "data": paginated_response.data['results']
            })
            
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "Notes retrieved successfully",
            "count": len(serializer.data),
            "data": serializer.data
        })

class NotesDetailView(generics.RetrieveUpdateAPIView):
    """
    API view to retrieve or update notes
    """
    serializer_class = NotesSerializer
    
    def get_queryset(self):
        return Notes.objects.filter(filing_id=self.kwargs['filing_id'])
    
    def get_object(self):
        queryset = self.get_queryset()
        return queryset.first()
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "message": "Notes retrieved successfully",
            "data": serializer.data
        })
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response({
            "success": True,
            "message": "Notes updated successfully",
            "data": serializer.data
        })

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
            return Response({
                "success": True,
                "message": "Search results retrieved successfully",
                "count": paginated_response.data['count'],
                "next": paginated_response.data['next'],
                "previous": paginated_response.data['previous'],
                "data": paginated_response.data['results']
            })
            
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "Search results retrieved successfully",
            "count": len(serializer.data),
            "data": serializer.data
        })

@api_view(['GET'])
def get_xbrl_by_uen(request, uen):
    """
    Retrieve XBRL data by UEN (Unique Entity Number)
    """
    try:
        xbrl = PartialXBRL.objects.get(filing_information__unique_entity_number=uen)
        serializer = PartialXBRLSerializer(xbrl)
        return Response({
            "success": True,
            "message": f"XBRL filing with UEN {uen} retrieved successfully",
            "data": serializer.data
        })
    except PartialXBRL.DoesNotExist:
        return Response({
            "success": False,
            "message": f"XBRL data not found for UEN {uen}"
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
def get_xbrl_template(request):
    """
    Get an empty XBRL JSON template
    """
    template = {
        "filing_information": {
            "company_name": "",
            "unique_entity_number": "",
            "current_period_start": "YYYY-MM-DD",
            "current_period_end": "YYYY-MM-DD",
            "prior_period_start": "YYYY-MM-DD",
            "xbrl_filing_type": "",
            "financial_statement_type": "",
            "accounting_standard": "",
            "authorisation_date": "YYYY-MM-DD",
            "financial_position_type": "",
            "is_going_concern": True,
            "has_comparative_changes": False,
            "presentation_currency": "",
            "functional_currency": "",
            "rounding_level": "",
            "entity_operations_description": "",
            "principal_place_of_business": "",
            "has_more_than_50_employees": False,
            "parent_entity_name": "",
            "ultimate_parent_name": "",
            "taxonomy_version": "2022.2",
            "xbrl_software": "",
            "xbrl_preparation_method": ""
        },
        "directors_statement": {
            "directors_opinion_true_fair_view": True,
            "reasonable_grounds_company_debts": True
        },
        "audit_report": {
            "audit_opinion": "",
            "auditing_standards": "",
            "material_uncertainty_going_concern": False,
            "proper_accounting_records": True
        },
        "statement_of_financial_position": {
            "total_assets": 0.0,
            "total_liabilities": 0.0,
            "current_assets": {
                "cash_and_bank_balances": 0.0,
                "trade_and_other_receivables": 0.0,
                "current_finance_lease_receivables": 0.0,
                "current_derivative_financial_assets": 0.0,
                "current_financial_assets_at_fair_value": 0.0,
                "other_current_financial_assets": 0.0,
                "development_properties": 0.0,
                "inventories": 0.0,
                "other_current_nonfinancial_assets": 0.0,
                "held_for_sale_assets": 0.0,
                "total_current_assets": 0.0
            },
            "noncurrent_assets": {
                "trade_and_other_receivables": 0.0,
                "noncurrent_finance_lease_receivables": 0.0,
                "noncurrent_derivative_financial_assets": 0.0,
                "noncurrent_financial_assets_at_fair_value": 0.0,
                "other_noncurrent_financial_assets": 0.0,
                "property_plant_equipment": 0.0,
                "investment_properties": 0.0,
                "goodwill": 0.0,
                "intangible_assets": 0.0,
                "investments_in_entities": 0.0,
                "deferred_tax_assets": 0.0,
                "other_noncurrent_nonfinancial_assets": 0.0,
                "total_noncurrent_assets": 0.0
            },
            "current_liabilities": {
                "trade_and_other_payables": 0.0,
                "current_loans_and_borrowings": 0.0,
                "current_financial_liabilities_at_fair_value": 0.0,
                "current_finance_lease_liabilities": 0.0,
                "other_current_financial_liabilities": 0.0,
                "current_income_tax_liabilities": 0.0,
                "current_provisions": 0.0,
                "other_current_nonfinancial_liabilities": 0.0,
                "liabilities_held_for_sale": 0.0,
                "total_current_liabilities": 0.0
            },
            "noncurrent_liabilities": {
                "trade_and_other_payables": 0.0,
                "noncurrent_loans_and_borrowings": 0.0,
                "noncurrent_financial_liabilities_at_fair_value": 0.0,
                "noncurrent_finance_lease_liabilities": 0.0,
                "other_noncurrent_financial_liabilities": 0.0,
                "deferred_tax_liabilities": 0.0,
                "noncurrent_provisions": 0.0,
                "other_noncurrent_nonfinancial_liabilities": 0.0,
                "total_noncurrent_liabilities": 0.0
            },
            "equity": {
                "share_capital": 0.0,
                "treasury_shares": 0.0,
                "accumulated_profits_losses": 0.0,
                "other_reserves": 0.0,
                "noncontrolling_interests": 0.0,
                "total_equity": 0.0
            }
        },
        "income_statement": {
            "revenue": 0.0,
            "other_income": 0.0,
            "employee_expenses": 0.0,
            "depreciation_expense": 0.0,
            "amortisation_expense": 0.0,
            "repairs_and_maintenance_expense": 0.0,
            "sales_and_marketing_expense": 0.0,
            "other_expenses_by_nature": 0.0,
            "other_gains_losses": 0.0,
            "finance_costs": 0.0,
            "share_of_profit_loss_of_associates_and_joint_ventures_accounted_for_using_equity_method": 0.0,
            "profit_loss_before_taxation": 0.0,
            "tax_expense_benefit_continuing_operations": 0.0,
            "profit_loss_from_discontinued_operations": 0.0,
            "profit_loss": 0.0,
            "profit_loss_attributable_to_owners_of_company": 0.0,
            "profit_loss_attributable_to_noncontrolling_interests": 0.0
        },
        "notes": {
            "trade_and_other_receivables": {
                "receivables_from_third_parties": 0.0,
                "receivables_from_related_parties": 0.0,
                "unbilled_receivables": 0.0,
                "other_receivables": 0.0,
                "total_trade_and_other_receivables": 0.0
            },
            "trade_and_other_payables": {
                "receivables_from_third_parties": 0.0,
                "receivables_from_related_parties": 0.0,
                "unbilled_receivables": 0.0,
                "other_receivables": 0.0,
                "total_trade_and_other_receivables": 0.0
            }
        }
    }
    
    return Response({
        "success": True,
        "message": "XBRL template generated successfully",
        "data": template
    })

@api_view(['POST'])
def validate_xbrl_json(request):
    """
    Validate XBRL JSON data without saving to database
    """
    try:
        # Normalize field names if needed
        if "filing_information" in request.data:
            request.data["filing_information"] = normalize_filing_information(request.data["filing_information"])
            
        serializer = PartialXBRLSerializer(data=request.data)
        if serializer.is_valid():
            return Response({
                "success": True,
                "message": "The provided JSON is valid XBRL data"
            })
        return Response({
            "success": False,
            "message": "Validation failed",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            "success": False,
            "message": "An error occurred during validation",
            "error": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def bulk_operations(request):
    """
    Handle bulk operations for XBRL data
    """
    operation = request.data.get('operation')
    
    if operation == 'import':
        items = request.data.get('items', [])
        results = []
        
        for item in items:
            try:
                # Normalize field names if needed
                if "filing_information" in item:
                    item["filing_information"] = normalize_filing_information(item["filing_information"])
                
                serializer = PartialXBRLSerializer(data=item)
                if serializer.is_valid():
                    xbrl = serializer.save()
                    results.append({
                        'status': 'success',
                        'id': xbrl.id,
                        'uen': xbrl.filing_information.unique_entity_number
                    })
                else:
                    results.append({
                        'status': 'error',
                        'message': serializer.errors,
                        'data': item.get('filing_information', {}).get('unique_entity_number', 'Unknown UEN')
                    })
            except Exception as e:
                results.append({
                    'status': 'error',
                    'message': str(e),
                    'data': item.get('filing_information', {}).get('unique_entity_number', 'Unknown UEN')
                })
        
        return Response({
            "success": True,
            "message": f"Bulk import completed with {len([r for r in results if r['status'] == 'success'])} successes and {len([r for r in results if r['status'] == 'error'])} errors",
            "results": results
        })
    
    elif operation == 'export':
        uens = request.data.get('uens', [])
        results = []
        
        for uen in uens:
            try:
                xbrl = PartialXBRL.objects.get(filing_information__unique_entity_number=uen)
                serializer = PartialXBRLSerializer(xbrl)
                results.append({
                    'status': 'success',
                    'uen': uen,
                    'data': serializer.data
                })
            except PartialXBRL.DoesNotExist:
                results.append({
                    'status': 'error',
                    'message': f'XBRL data not found for UEN: {uen}',
                    'uen': uen
                })
        
        return Response({
            "success": True,
            "message": f"Bulk export completed with {len([r for r in results if r['status'] == 'success'])} successes and {len([r for r in results if r['status'] == 'error'])} errors",
            "results": results
        })
    
    elif operation == 'delete':
        uens = request.data.get('uens', [])
        results = []
        
        for uen in uens:
            try:
                xbrl = PartialXBRL.objects.get(filing_information__unique_entity_number=uen)
                xbrl.delete()  # This should cascade delete all related objects
                results.append({
                    'status': 'success',
                    'message': f'Successfully deleted XBRL data for UEN: {uen}',
                    'uen': uen
                })
            except PartialXBRL.DoesNotExist:
                results.append({
                    'status': 'error',
                    'message': f'XBRL data not found for UEN: {uen}',
                    'uen': uen
                })
        
        return Response({
            "success": True,
            "message": f"Bulk delete completed with {len([r for r in results if r['status'] == 'success'])} successes and {len([r for r in results if r['status'] == 'error'])} errors",
            "results": results
        })
    
    return Response({
        "success": False,
        "message": "Invalid operation",
        "error": "The operation must be one of: import, export, delete"
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def map_financial_data(request):
    """
    Map financial statement data to standard format and store in database
    """
    try:
        logfire.info("Starting financial data mapping process")
        
        # Extract data from request
        data = request.data.get('data', {})
        
        # Convert to JSON string for processing
        data_json = json.dumps(data, indent=4)
        logfire.debug("Input data prepared", data_size=len(data_json))
        
        # Use asyncio to run the async function in a sync view
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Run the financial statement agent
            logfire.info("Executing financial statement agent")
            result_mapping = loop.run_until_complete(
                financial_statement_agent.run(
                    f'Please map this financial statement data: {data_json}',
                    deps=financial_deps
                )
            )
            logfire.info("Financial statement agent completed successfully")
        except Exception as e:
            logfire.exception("Error during financial statement agent execution", error=str(e))
            raise
        finally:
            loop.close()
        
        # Convert result to dictionary
        logfire.debug("Processing agent results")
        if hasattr(result_mapping.data, 'model_dump'):  # Pydantic v2
            mapped_data_dict = result_mapping.data.model_dump()
        elif hasattr(result_mapping.data, 'dict'):      # Pydantic v1
            mapped_data_dict = result_mapping.data.dict()
        else:
            # Fallback to manual conversion
            mapped_data_dict = {k: v for k, v in result_mapping.data.__dict__.items() 
                              if not k.startswith('_')}
        
        logfire.info("Financial data mapping completed successfully")
        
        # Store mapped data in database
        try:
            filing_id = store_mapped_data_to_db(mapped_data_dict)
            logfire.info(f"Successfully stored mapped data in database with ID: {filing_id}")
            
            # Return success response with mapped data and filing ID
            return success_response(
                message="Financial data mapped and stored successfully",
                data={
                    "filing_id": str(filing_id),
                    "mapped_data": mapped_data_dict
                }
            )
        except Exception as db_error:
            logfire.exception("Error storing mapped data in database", error=str(db_error))
            # Return the mapped data even if storage failed
            return error_response(
                message="Financial data was mapped but could not be stored in the database",
                error=str(db_error),
                data={"mapped_data": mapped_data_dict},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        # Enhanced error logging with more details
        error_type = type(e).__name__
        error_details = str(e)
        
        logfire.exception(
            "Error during financial data mapping", 
            error=error_details,
            error_type=error_type
        )
        
        # Return error response
        return error_response(
            message="Failed to map financial data",
            error=error_details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def map_pydantic_to_django_fields(pydantic_data_dict):
    """
    Maps field names from Pydantic models (PascalCase) to Django models (snake_case)
    
    Args:
        pydantic_data_dict (dict): Data dictionary from AI mapping agent with PascalCase keys
        
    Returns:
        dict: Mapped dictionary with snake_case keys for Django models
    """
    # FilingInformation field mapping
    filing_info_mapping = {
        # Basic fields
        'NameOfCompany': 'company_name',
        'UniqueEntityNumber': 'unique_entity_number',
        'CurrentPeriodStartDate': 'current_period_start',
        'CurrentPeriodEndDate': 'current_period_end',
        'PriorPeriodStartDate': 'prior_period_start',
        
        # XBRL Filing info
        'TypeOfXBRLFiling': 'xbrl_filing_type',
        'NatureOfFinancialStatementsCompanyLevelOrConsolidated': 'financial_statement_type',
        'TypeOfAccountingStandardUsedToPrepareFinancialStatements': 'accounting_standard',
        'DateOfAuthorisationForIssueOfFinancialStatements': 'authorisation_date',
        'TypeOfStatementOfFinancialPosition': 'financial_position_type',
        
        # Financial statement characteristics
        'WhetherTheFinancialStatementsArePreparedOnGoingConcernBasis': 'is_going_concern',
        'WhetherThereAreAnyChangesToComparativeAmounts': 'has_comparative_changes',
        'DescriptionOfPresentationCurrency': 'presentation_currency',
        'DescriptionOfFunctionalCurrency': 'functional_currency',
        'LevelOfRoundingUsedInFinancialStatements': 'rounding_level',
        'DescriptionOfNatureOfEntitysOperationsAndPrincipalActivities': 'entity_operations_description',
        
        # Company details
        'PrincipalPlaceOfBusinessIfDifferentFromRegisteredOffice': 'principal_place_of_business',
        'WhetherCompanyOrGroupIfConsolidatedAccountsArePreparedHasMoreThan50Employees': 'has_more_than_50_employees',
        'NameOfParentEntity': 'parent_entity_name',
        'NameOfUltimateParentOfGroup': 'ultimate_parent_name',
        'TaxonomyVersion': 'taxonomy_version',
        'NameAndVersionOfSoftwareUsedToGenerateXBRLFile': 'xbrl_software',
        'HowWasXBRLFilePrepared': 'xbrl_preparation_method',
    }
    
    # DirectorsStatement field mapping
    directors_statement_mapping = {
        'WhetherInDirectorsOpinionFinancialStatementsAreDrawnUpSoAsToExhibitATrueAndFairView': 'directors_opinion_true_fair_view',
        'WhetherThereAreReasonableGroundsToBelieveThatCompanyWillBeAbleToPayItsDebtsAsAndWhenTheyFallDueAtDateOfStatement': 'reasonable_grounds_company_debts',
    }
    
    # AuditReport field mapping
    audit_report_mapping = {
        'TypeOfAuditOpinionInIndependentAuditorsReport': 'audit_opinion',
        'AuditingStandardsUsedToConductTheAudit': 'auditing_standards',
        'WhetherThereIsAnyMaterialUncertaintyRelatingToGoingConcern': 'material_uncertainty_going_concern',
        'WhetherInAuditorsOpinionAccountingAndOtherRecordsRequiredAreProperlyKept': 'proper_accounting_records',
    }
    
    # CurrentAssets field mapping
    current_assets_mapping = {
        'CashAndBankBalances': 'cash_and_bank_balances',
        'TradeAndOtherReceivablesCurrent': 'trade_and_other_receivables',
        'CurrentFinanceLeaseReceivables': 'current_finance_lease_receivables',
        'CurrentDerivativeFinancialAssets': 'current_derivative_financial_assets',
        'CurrentFinancialAssetsMeasuredAtFairValueThroughProfitOrLoss': 'current_financial_assets_at_fair_value',
        'OtherCurrentFinancialAssets': 'other_current_financial_assets',
        'DevelopmentProperties': 'development_properties',
        'Inventories': 'inventories',
        'OtherCurrentNonfinancialAssets': 'other_current_nonfinancial_assets',
        'NoncurrentAssetsOrDisposalGroupsClassifiedAsHeldForSaleOrAsHeldForDistributionToOwners': 'held_for_sale_assets',
        'CurrentAssets': 'total_current_assets',
    }
    
    # NonCurrentAssets field mapping
    noncurrent_assets_mapping = {
        'TradeAndOtherReceivablesNoncurrent': 'trade_and_other_receivables',
        'NoncurrentFinanceLeaseReceivables': 'noncurrent_finance_lease_receivables',
        'NoncurrentDerivativeFinancialAssets': 'noncurrent_derivative_financial_assets',
        'NoncurrentFinancialAssetsMeasuredAtFairValueThroughProfitOrLoss': 'noncurrent_financial_assets_at_fair_value',
        'OtherNoncurrentFinancialAssets': 'other_noncurrent_financial_assets',
        'PropertyPlantAndEquipment': 'property_plant_equipment',
        'InvestmentProperties': 'investment_properties',
        'Goodwill': 'goodwill',
        'IntangibleAssetsOtherThanGoodwill': 'intangible_assets',
        'InvestmentsInSubsidiariesAssociatesOrJointVentures': 'investments_in_entities',
        'DeferredTaxAssets': 'deferred_tax_assets',
        'OtherNoncurrentNonfinancialAssets': 'other_noncurrent_nonfinancial_assets',
        'NoncurrentAssets': 'total_noncurrent_assets',
    }
    
    # CurrentLiabilities field mapping
    current_liabilities_mapping = {
        'TradeAndOtherPayablesCurrent': 'trade_and_other_payables',
        'CurrentLoansAndBorrowings': 'current_loans_and_borrowings',
        'CurrentFinancialLiabilitiesMeasuredAtFairValueThroughProfitOrLoss': 'current_financial_liabilities_at_fair_value',
        'CurrentFinanceLeaseLiabilities': 'current_finance_lease_liabilities',
        'OtherCurrentFinancialLiabilities': 'other_current_financial_liabilities',
        'CurrentIncomeTaxLiabilities': 'current_income_tax_liabilities',
        'CurrentProvisions': 'current_provisions',
        'OtherCurrentNonfinancialLiabilities': 'other_current_nonfinancial_liabilities',
        'LiabilitiesClassifiedAsHeldForSale': 'liabilities_held_for_sale',
        'CurrentLiabilities': 'total_current_liabilities',
    }
    
    # NonCurrentLiabilities field mapping
    noncurrent_liabilities_mapping = {
        'TradeAndOtherPayablesNoncurrent': 'trade_and_other_payables',
        'NoncurrentLoansAndBorrowings': 'noncurrent_loans_and_borrowings',
        'NoncurrentFinancialLiabilitiesMeasuredAtFairValueThroughProfitOrLoss': 'noncurrent_financial_liabilities_at_fair_value',
        'NoncurrentFinanceLeaseLiabilities': 'noncurrent_finance_lease_liabilities',
        'OtherNoncurrentFinancialLiabilities': 'other_noncurrent_financial_liabilities',
        'DeferredTaxLiabilities': 'deferred_tax_liabilities',
        'NoncurrentProvisions': 'noncurrent_provisions',
        'OtherNoncurrentNonfinancialLiabilities': 'other_noncurrent_nonfinancial_liabilities',
        'NoncurrentLiabilities': 'total_noncurrent_liabilities',
    }
    
    # Equity field mapping
    equity_mapping = {
        'ShareCapital': 'share_capital',
        'TreasuryShares': 'treasury_shares',
        'AccumulatedProfitsLosses': 'accumulated_profits_losses',
        'ReservesOtherThanAccumulatedProfitsLosses': 'other_reserves',
        'NoncontrollingInterests': 'noncontrolling_interests',
        'Equity': 'total_equity',
    }
    
    # IncomeStatement field mapping
    income_statement_mapping = {
        'Revenue': 'revenue',
        'OtherIncome': 'other_income',
        'EmployeeBenefitsExpense': 'employee_expenses',
        'DepreciationExpense': 'depreciation_expense',
        'AmortisationExpense': 'amortisation_expense',
        'RepairsAndMaintenanceExpense': 'repairs_and_maintenance_expense',
        'SalesAndMarketingExpense': 'sales_and_marketing_expense',
        'OtherExpensesByNature': 'other_expenses_by_nature',
        'OtherGainsLosses': 'other_gains_losses',
        'FinanceCosts': 'finance_costs',
        'ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod': 'share_of_profit_loss_of_associates_and_joint_ventures_accounted_for_using_equity_method',
        'ProfitLossBeforeTaxation': 'profit_loss_before_taxation',
        'TaxExpenseBenefitContinuingOperations': 'tax_expense_benefit_continuing_operations',
        'ProfitLossFromDiscontinuedOperations': 'profit_loss_from_discontinued_operations',
        'ProfitLoss': 'profit_loss',
        'ProfitLossAttributableToOwnersOfCompany': 'profit_loss_attributable_to_owners_of_company',
        'ProfitLossAttributableToNoncontrollingInterests': 'profit_loss_attributable_to_noncontrolling_interests',
    }
    
    # TradeAndOtherReceivables field mapping
    trade_receivables_mapping = {
        'TradeAndOtherReceivablesDueFromThirdParties': 'receivables_from_third_parties',
        'TradeAndOtherReceivablesDueFromRelatedParties': 'receivables_from_related_parties',
        'UnbilledReceivables': 'unbilled_receivables',
        'OtherReceivables': 'other_receivables',
        'TradeAndOtherReceivables': 'total_trade_and_other_receivables',
    }
    
    # TradeAndOtherPayables field mapping
    trade_payables_mapping = {
        'TradeAndOtherPayablesDueToThirdParties': 'payables_to_third_parties',
        'TradeAndOtherPayablesDueToRelatedParties': 'payables_to_related_parties',
        'DeferredIncome': 'deferred_income',
        'OtherPayables': 'other_payables',
        'TradeAndOtherPayables': 'total_trade_and_other_payables',
    }
    
    # Revenue field mapping
    revenue_mapping = {
        'RevenueFromPropertyTransferredAtPointInTime': 'revenue_from_property_point_in_time',
        'RevenueFromGoodsTransferredAtPointInTime': 'revenue_from_goods_point_in_time',
        'RevenueFromServicesTransferredAtPointInTime': 'revenue_from_services_point_in_time',
        'RevenueFromPropertyTransferredOverTime': 'revenue_from_property_over_time',
        'RevenueFromConstructionContractsOverTime': 'revenue_from_construction_over_time',
        'RevenueFromServicesTransferredOverTime': 'revenue_from_services_over_time',
        'OtherRevenue': 'other_revenue',
        'Revenue': 'total_revenue',
    }
    
    # Create a new dictionary with mapped field names
    mapped_data = {}
    
    # Map FilingInformation section
    if 'FilingInformation' in pydantic_data_dict:
        filing_info = pydantic_data_dict['FilingInformation']
        mapped_filing_info = {}
        
        for pascal_name, snake_name in filing_info_mapping.items():
            if pascal_name in filing_info:
                mapped_filing_info[snake_name] = filing_info[pascal_name]
        
        mapped_data['filing_information'] = mapped_filing_info
    
    # Map DirectorsStatement section
    if 'DirectorsStatement' in pydantic_data_dict:
        directors_statement = pydantic_data_dict['DirectorsStatement']
        mapped_directors_statement = {}
        
        for pascal_name, snake_name in directors_statement_mapping.items():
            if pascal_name in directors_statement:
                mapped_directors_statement[snake_name] = directors_statement[pascal_name]
        
        mapped_data['directors_statement'] = mapped_directors_statement
    
    # Map AuditReport section
    if 'AuditReport' in pydantic_data_dict:
        audit_report = pydantic_data_dict['AuditReport']
        mapped_audit_report = {}
        
        for pascal_name, snake_name in audit_report_mapping.items():
            if pascal_name in audit_report:
                mapped_audit_report[snake_name] = audit_report[pascal_name]
        
        mapped_data['audit_report'] = mapped_audit_report
    
    # Map StatementOfFinancialPosition section
    if 'StatementOfFinancialPosition' in pydantic_data_dict:
        financial_position = pydantic_data_dict['StatementOfFinancialPosition']
        mapped_financial_position = {}
        
        # Map total assets and liabilities
        if 'Assets' in financial_position:
            mapped_financial_position['total_assets'] = financial_position['Assets']
        if 'Liabilities' in financial_position:
            mapped_financial_position['total_liabilities'] = financial_position['Liabilities']
        
        # Map CurrentAssets subsection
        if 'CurrentAssets' in financial_position:
            current_assets = financial_position['CurrentAssets']
            mapped_current_assets = {}
            
            for pascal_name, snake_name in current_assets_mapping.items():
                if pascal_name in current_assets:
                    mapped_current_assets[snake_name] = current_assets[pascal_name]
            
            mapped_financial_position['current_assets'] = mapped_current_assets
        
        # Map NonCurrentAssets subsection
        if 'NonCurrentAssets' in financial_position:
            noncurrent_assets = financial_position['NonCurrentAssets']
            mapped_noncurrent_assets = {}
            
            for pascal_name, snake_name in noncurrent_assets_mapping.items():
                if pascal_name in noncurrent_assets:
                    mapped_noncurrent_assets[snake_name] = noncurrent_assets[pascal_name]
            
            mapped_financial_position['noncurrent_assets'] = mapped_noncurrent_assets
        
        # Map CurrentLiabilities subsection
        if 'CurrentLiabilities' in financial_position:
            current_liabilities = financial_position['CurrentLiabilities']
            mapped_current_liabilities = {}
            
            for pascal_name, snake_name in current_liabilities_mapping.items():
                if pascal_name in current_liabilities:
                    mapped_current_liabilities[snake_name] = current_liabilities[pascal_name]
            
            mapped_financial_position['current_liabilities'] = mapped_current_liabilities
        
        # Map NonCurrentLiabilities subsection
        if 'NonCurrentLiabilities' in financial_position:
            noncurrent_liabilities = financial_position['NonCurrentLiabilities']
            mapped_noncurrent_liabilities = {}
            
            for pascal_name, snake_name in noncurrent_liabilities_mapping.items():
                if pascal_name in noncurrent_liabilities:
                    mapped_noncurrent_liabilities[snake_name] = noncurrent_liabilities[pascal_name]
            
            mapped_financial_position['noncurrent_liabilities'] = mapped_noncurrent_liabilities
        
        # Map Equity subsection
        if 'Equity' in financial_position:
            equity = financial_position['Equity']
            mapped_equity = {}
            
            for pascal_name, snake_name in equity_mapping.items():
                if pascal_name in equity:
                    mapped_equity[snake_name] = equity[pascal_name]
            
            mapped_financial_position['equity'] = mapped_equity
        
        mapped_data['statement_of_financial_position'] = mapped_financial_position
    
    # Map IncomeStatement section
    if 'IncomeStatement' in pydantic_data_dict:
        income_statement = pydantic_data_dict['IncomeStatement']
        mapped_income_statement = {}
        
        for pascal_name, snake_name in income_statement_mapping.items():
            if pascal_name in income_statement:
                mapped_income_statement[snake_name] = income_statement[pascal_name]
        
        mapped_data['income_statement'] = mapped_income_statement
    
    # Map Notes section
    if 'Notes' in pydantic_data_dict:
        notes = pydantic_data_dict['Notes']
        mapped_notes = {}
        
        # Map TradeAndOtherReceivables subsection
        if 'TradeAndOtherReceivables' in notes:
            trade_receivables = notes['TradeAndOtherReceivables']
            mapped_trade_receivables = {}
            
            for pascal_name, snake_name in trade_receivables_mapping.items():
                if pascal_name in trade_receivables:
                    mapped_trade_receivables[snake_name] = trade_receivables[pascal_name]
            
            mapped_notes['trade_and_other_receivables'] = mapped_trade_receivables
        
        # Map TradeAndOtherPayables subsection
        if 'TradeAndOtherPayables' in notes:
            trade_payables = notes['TradeAndOtherPayables']
            mapped_trade_payables = {}
            
            for pascal_name, snake_name in trade_payables_mapping.items():
                if pascal_name in trade_payables:
                    mapped_trade_payables[snake_name] = trade_payables[pascal_name]
            
            mapped_notes['trade_and_other_payables'] = mapped_trade_payables
        
        # Map Revenue subsection
        if 'Revenue' in notes:
            revenue = notes['Revenue']
            mapped_revenue = {}
            
            for pascal_name, snake_name in revenue_mapping.items():
                if pascal_name in revenue:
                    mapped_revenue[snake_name] = revenue[pascal_name]
            
            mapped_notes['revenue'] = mapped_revenue
        
        mapped_data['notes'] = mapped_notes
    
    # Add any top-level fields that might be useful
    if 'company_name' not in mapped_data.get('filing_information', {}) and 'NameOfCompany' in pydantic_data_dict:
        if 'filing_information' not in mapped_data:
            mapped_data['filing_information'] = {}
        mapped_data['filing_information']['company_name'] = pydantic_data_dict['NameOfCompany']
    
    if 'unique_entity_number' not in mapped_data.get('filing_information', {}) and 'UniqueEntityNumber' in pydantic_data_dict:
        if 'filing_information' not in mapped_data:
            mapped_data['filing_information'] = {}
        mapped_data['filing_information']['unique_entity_number'] = pydantic_data_dict['UniqueEntityNumber']
    
    return mapped_data

def store_mapped_data_to_db(mapped_data_dict):
    """
    Store mapped financial data to the database
    
    Args:
        mapped_data_dict (dict): Dictionary containing mapped financial data (in PascalCase or snake_case)
        
    Returns:
        uuid: ID of the created XBRL filing
        
    Raises:
        ValueError: If required data is missing
        ValidationError: If data validation fails
        Exception: For other database errors
    """
    with transaction.atomic():
        try:
            logfire.info("Started storing mapped data to database")
            
            # First, convert all PascalCase field names to snake_case using the existing mapping function
            mapped_data_dict = map_pydantic_to_django_fields(mapped_data_dict)
            logfire.debug("Pydantic data mapped to Django field names", 
                         top_level_keys=list(mapped_data_dict.keys()))
            
            # Extract and normalize data sections
            filing_info_data = mapped_data_dict.get('filing_information', {})
            
            # Validate company name and UEN
            if not filing_info_data.get('company_name'):
                logfire.error("Company name not found in mapped data", 
                             mapped_data_keys=list(mapped_data_dict.keys()),
                             filing_info_keys=list(filing_info_data.keys()))
                raise ValueError("Company name is required")
                
            if not filing_info_data.get('unique_entity_number'):
                logfire.error("UEN not found in mapped data", 
                             mapped_data_keys=list(mapped_data_dict.keys()),
                             filing_info_keys=list(filing_info_data.keys()))
                raise ValueError("Unique Entity Number (UEN) is required")
            
            # Add default values for required fields if not present
            default_filing_info = {
                'current_period_start': '2023-01-01',
                'current_period_end': '2023-12-31',
                'xbrl_filing_type': 'PARTIAL',
                'financial_statement_type': 'COMPANY_LEVEL',
                'accounting_standard': 'SFRS',
                'authorisation_date': '2024-01-15',
                'financial_position_type': 'CURRENT_NONCURRENT',
                'is_going_concern': True,
                'has_comparative_changes': False,
                'presentation_currency': 'SGD',
                'functional_currency': 'SGD',
                'rounding_level': 'UNIT',
                'entity_operations_description': 'Business operations and activities in Singapore.',
                'principal_place_of_business': 'Singapore',
                'has_more_than_50_employees': False,
                'taxonomy_version': '2022.2',
                'xbrl_software': 'AI XBRL Assistant',
                'xbrl_preparation_method': 'AUTOMATED'
            }
            
            # Update filing_info_data with default values only for missing fields
            for field, default_value in default_filing_info.items():
                if field not in filing_info_data or filing_info_data[field] is None:
                    filing_info_data[field] = default_value
            
            # Extract remaining data sections
            directors_statement_data = mapped_data_dict.get('directors_statement', {})
            audit_report_data = mapped_data_dict.get('audit_report', {})
            financial_position_data = mapped_data_dict.get('statement_of_financial_position', {})
            current_assets_data = financial_position_data.get('current_assets', {})
            noncurrent_assets_data = financial_position_data.get('noncurrent_assets', {})
            current_liabilities_data = financial_position_data.get('current_liabilities', {})
            noncurrent_liabilities_data = financial_position_data.get('noncurrent_liabilities', {})
            equity_data = financial_position_data.get('equity', {})
            income_statement_data = mapped_data_dict.get('income_statement', {})
            notes_data = mapped_data_dict.get('notes', {})
            trade_receivables_data = notes_data.get('trade_and_other_receivables', {})
            trade_payables_data = notes_data.get('trade_and_other_payables', {})
            revenue_data = notes_data.get('revenue', {})
            
            # Default values for remaining required sections
            if not directors_statement_data:
                directors_statement_data = {
                    "directors_opinion_true_fair_view": True, 
                    "reasonable_grounds_company_debts": True
                }
                
            if not audit_report_data:
                audit_report_data = {
                    "audit_opinion": "Unqualified", 
                    "proper_accounting_records": True
                }
            
            # Default for equity if missing
            if not equity_data:
                equity_data = {
                    "share_capital": 1,
                    "accumulated_profits_losses": 0,
                    "total_equity": 1
                }
            
            # Default for assets/liabilities totals
            if 'total_current_assets' not in current_assets_data:
                current_assets_data['total_current_assets'] = 0
            
            if 'total_noncurrent_assets' not in noncurrent_assets_data:
                noncurrent_assets_data['total_noncurrent_assets'] = 0
                
            if 'total_current_liabilities' not in current_liabilities_data:
                current_liabilities_data['total_current_liabilities'] = 0
                
            if 'total_noncurrent_liabilities' not in noncurrent_liabilities_data:
                noncurrent_liabilities_data['total_noncurrent_liabilities'] = 0
                
            # Default for total revenue
            if not revenue_data:
                revenue_data = {"total_revenue": 0}
            elif 'total_revenue' not in revenue_data:
                revenue_data['total_revenue'] = 0
                
            # Default for receivables/payables totals
            if not trade_receivables_data:
                trade_receivables_data = {"total_trade_and_other_receivables": 0}
            elif 'total_trade_and_other_receivables' not in trade_receivables_data:
                trade_receivables_data['total_trade_and_other_receivables'] = 0
                
            if not trade_payables_data:
                trade_payables_data = {"total_trade_and_other_payables": 0}
            elif 'total_trade_and_other_payables' not in trade_payables_data:
                trade_payables_data['total_trade_and_other_payables'] = 0
            
            # Create filing information
            logfire.debug("Creating filing information record", company_name=filing_info_data.get('company_name'))
            filing_info_serializer = FilingInformationSerializer(data=filing_info_data)
            if not filing_info_serializer.is_valid():
                logfire.error("Invalid filing information", errors=filing_info_serializer.errors)
                raise ValueError(f"Invalid filing information: {filing_info_serializer.errors}")
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
            total_assets = financial_position_data.get('total_assets', 
                                                      current_assets_data.get('total_current_assets', 0) +
                                                      noncurrent_assets_data.get('total_noncurrent_assets', 0))
            
            total_liabilities = financial_position_data.get('total_liabilities',
                                                          current_liabilities_data.get('total_current_liabilities', 0) +
                                                          noncurrent_liabilities_data.get('total_noncurrent_liabilities', 0))
            
            sof_position = StatementOfFinancialPosition.objects.create(
                filing=filing_info,
                current_assets=current_assets,
                noncurrent_assets=noncurrent_assets,
                current_liabilities=current_liabilities,
                noncurrent_liabilities=noncurrent_liabilities,
                equity=equity,
                total_assets=total_assets,
                total_liabilities=total_liabilities
            )
            
            # Create income statement with defaults for required fields
            if 'profit_loss_before_taxation' not in income_statement_data:
                income_statement_data['profit_loss_before_taxation'] = 0
                
            if 'tax_expense_benefit_continuing_operations' not in income_statement_data:
                income_statement_data['tax_expense_benefit_continuing_operations'] = 0
                
            if 'profit_loss' not in income_statement_data:
                income_statement_data['profit_loss'] = 0
                
            if 'profit_loss_attributable_to_owners_of_company' not in income_statement_data:
                income_statement_data['profit_loss_attributable_to_owners_of_company'] = 0
                
            if 'revenue' not in income_statement_data:
                income_statement_data['revenue'] = 0
            
            income_statement = IncomeStatement.objects.create(
                filing=filing_info, 
                **income_statement_data
            )
            
            # Create Trade and Other Receivables
            trade_receivables = TradeAndOtherReceivables.objects.create(
                filing=filing_info, 
                **trade_receivables_data
            )
            
            # Create Trade and Other Payables
            trade_payables = TradeAndOtherPayables.objects.create(
                filing=filing_info, 
                **trade_payables_data
            )
            
            # Create Revenue
            revenue = Revenue.objects.create(
                filing=filing_info,
                **revenue_data
            )
            
            # Create notes with all required components
            notes = Notes.objects.create(
                filing=filing_info,
                trade_and_other_receivables=trade_receivables,
                trade_and_other_payables=trade_payables,
                revenue=revenue
            )
            
            # Create the main XBRL object
            xbrl = PartialXBRL.objects.create(
                filing_information=filing_info,
                directors_statement=directors_statement,
                audit_report=audit_report,
                statement_of_financial_position=sof_position,
                income_statement=income_statement,
                notes=notes
            )
            
            logfire.info(f"Successfully stored financial data in database with ID: {xbrl.id}",
                        company_name=filing_info_data.get('company_name'),
                        uen=filing_info_data.get('unique_entity_number'))
            return xbrl.id
            
        except Exception as e:
            logfire.exception(f"Error storing data in database: {str(e)}")
            raise