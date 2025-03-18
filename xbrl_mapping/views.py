# views.py (optimized)
from rest_framework import viewsets, status, generics, filters
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    PartialXBRL, FilingInformation, StatementOfFinancialPosition,
    IncomeStatement, Notes, DirectorsStatement, AuditReport, CurrentAssets,
    NonCurrentAssets, CurrentLiabilities, NonCurrentLiabilities, Equity,
    TradeAndOtherReceivables, TradeAndOtherPayables
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