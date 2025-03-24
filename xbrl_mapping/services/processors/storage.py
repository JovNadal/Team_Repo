"""
Data mapping services for XBRL processing.
Provides functions to map between different data formats and store mapped data.
"""
import logfire
from django.db import transaction


# Import the model from the Django app
from ...models import (
    PartialXBRL, FilingInformation, StatementOfFinancialPosition,
    IncomeStatement, Notes, DirectorsStatement, AuditReport, CurrentAssets,
    NonCurrentAssets, CurrentLiabilities, NonCurrentLiabilities, Equity,
    TradeAndOtherReceivables, TradeAndOtherPayables, Revenue
)
from ...serializers import FilingInformationSerializer

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