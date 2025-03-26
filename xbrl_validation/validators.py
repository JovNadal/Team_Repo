import re
import json
from decimal import Decimal
from typing import Dict, List, Any, Set, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class XBRLValidationError(Exception):
    """Custom exception for XBRL validation errors"""
    def __init__(self, error_dict: Dict[str, List[str]]):
        self.error_dict = error_dict
        super().__init__(str(error_dict))


class BaseXBRLValidator:
    """Base class for XBRL validation"""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.errors = {}
        
    def validate(self) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Validate the XBRL data
        Returns:
            Tuple containing:
            - Boolean indicating if validation passed
            - Dictionary of errors by section
        """
        # Run validation checks
        self._validate_required_sections()
        
        # Additional validation methods would be called here
        # Each validation method should add to self.errors
        
        return len(self.errors) == 0, self.errors
    
    def _validate_required_sections(self) -> None:
        """Validate that all required sections are present"""
        # ACRA requires these sections for all filings
        required_sections = {
            'FilingInformation',
            'StatementOfFinancialPosition',
            'IncomeStatement'
        }
        
        # Map for alternative section names
        section_mapping = {
            'FilingInformation': ['FilingInformation', 'filing_information'],
            'StatementOfFinancialPosition': ['StatementOfFinancialPosition', 'statement_of_financial_position'],
            'IncomeStatement': ['IncomeStatement', 'income_statement'],
            'DirectorsStatement': ['DirectorsStatement', 'directors_statement'],
            'AuditReport': ['AuditReport', 'audit_report'],
            'Notes': ['Notes', 'notes']
        }
        
        # Check for missing sections
        missing_sections = []
        
        for required_section in required_sections:
            section_found = False
            for alternative_name in section_mapping.get(required_section, [required_section]):
                if alternative_name in self.data:
                    section_found = True
                    break
            
            if not section_found:
                missing_sections.append(required_section)
        
        if missing_sections:
            self._add_error('structure', f"Missing required section(s): {', '.join(missing_sections)}")


class ACRAXBRLValidator:
    """ACRA-specific XBRL validation rules"""
    
    # Field mappings for XBRL validation
    FILING_INFO_MAPPING = {
        'NameOfCompany': 'company_name',
        'UniqueEntityNumber': 'unique_entity_number',
        'CurrentPeriodStartDate': 'current_period_start',
        'CurrentPeriodEndDate': 'current_period_end',
        'PriorPeriodStartDate': 'prior_period_start',
        'TypeOfXBRLFiling': 'xbrl_filing_type',
        'NatureOfFinancialStatementsCompanyLevelOrConsolidated': 'financial_statement_type',
        'TypeOfAccountingStandardUsedToPrepareFinancialStatements': 'accounting_standard',
        'DateOfAuthorisationForIssueOfFinancialStatements': 'authorisation_date',
        'TypeOfStatementOfFinancialPosition': 'financial_position_type',
        'WhetherTheFinancialStatementsArePreparedOnGoingConcernBasis': 'is_going_concern',
        'WhetherThereAreAnyChangesToComparativeAmounts': 'has_comparative_changes',
        'DescriptionOfPresentationCurrency': 'presentation_currency',
        'DescriptionOfFunctionalCurrency': 'functional_currency',
        'LevelOfRoundingUsedInFinancialStatements': 'rounding_level',
        'DescriptionOfNatureOfEntitysOperationsAndPrincipalActivities': 'entity_operations_description',
        'PrincipalPlaceOfBusinessIfDifferentFromRegisteredOffice': 'principal_place_of_business',
        'WhetherCompanyOrGroupIfConsolidatedAccountsArePreparedHasMoreThan50Employees': 'has_more_than_50_employees',
        'NameOfParentEntity': 'parent_entity_name',
        'NameOfUltimateParentOfGroup': 'ultimate_parent_name',
        'TaxonomyVersion': 'taxonomy_version',
        'NameAndVersionOfSoftwareUsedToGenerateXBRLFile': 'xbrl_software',
        'HowWasXBRLFilePrepared': 'xbrl_preparation_method'
    }

    CURRENT_ASSETS_MAPPING = {
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
        'CurrentAssets': 'total_current_assets'
    }

    NONCURRENT_ASSETS_MAPPING = {
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
        'NoncurrentAssets': 'total_noncurrent_assets'
    }

    CURRENT_LIABILITIES_MAPPING = {
        'TradeAndOtherPayablesCurrent': 'trade_and_other_payables',
        'CurrentLoansAndBorrowings': 'current_loans_and_borrowings',
        'CurrentFinancialLiabilitiesMeasuredAtFairValueThroughProfitOrLoss': 'current_financial_liabilities_at_fair_value',
        'CurrentFinanceLeaseLiabilities': 'current_finance_lease_liabilities',
        'OtherCurrentFinancialLiabilities': 'other_current_financial_liabilities',
        'CurrentIncomeTaxLiabilities': 'current_income_tax_liabilities',
        'CurrentProvisions': 'current_provisions',
        'OtherCurrentNonfinancialLiabilities': 'other_current_nonfinancial_liabilities',
        'LiabilitiesClassifiedAsHeldForSale': 'liabilities_held_for_sale',
        'CurrentLiabilities': 'total_current_liabilities'
    }

    NONCURRENT_LIABILITIES_MAPPING = {
        'TradeAndOtherPayablesNoncurrent': 'trade_and_other_payables',
        'NoncurrentLoansAndBorrowings': 'noncurrent_loans_and_borrowings',
        'NoncurrentFinancialLiabilitiesMeasuredAtFairValueThroughProfitOrLoss': 'noncurrent_financial_liabilities_at_fair_value',
        'NoncurrentFinanceLeaseLiabilities': 'noncurrent_finance_lease_liabilities',
        'OtherNoncurrentFinancialLiabilities': 'other_noncurrent_financial_liabilities',
        'DeferredTaxLiabilities': 'deferred_tax_liabilities',
        'NoncurrentProvisions': 'noncurrent_provisions',
        'OtherNoncurrentNonfinancialLiabilities': 'other_noncurrent_nonfinancial_liabilities',
        'NoncurrentLiabilities': 'total_noncurrent_liabilities'
    }

    EQUITY_MAPPING = {
        'ShareCapital': 'share_capital',
        'TreasuryShares': 'treasury_shares',
        'AccumulatedProfitsLosses': 'accumulated_profits_losses',
        'ReservesOtherThanAccumulatedProfitsLosses': 'other_reserves',
        'NoncontrollingInterests': 'noncontrolling_interests',
        'Equity': 'total_equity'
    }

    INCOME_STATEMENT_MAPPING = {
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
        'ProfitLossAttributableToNoncontrollingInterests': 'profit_loss_attributable_to_noncontrolling_interests'
    }

    NOTES_RECEIVABLES_MAPPING = {
        'TradeAndOtherReceivablesDueFromThirdParties': 'receivables_from_third_parties',
        'TradeAndOtherReceivablesDueFromRelatedParties': 'receivables_from_related_parties',
        'UnbilledReceivables': 'unbilled_receivables',
        'OtherReceivables': 'other_receivables',
        'TradeAndOtherReceivables': 'total_trade_and_other_receivables'
    }

    NOTES_PAYABLES_MAPPING = {
        'TradeAndOtherPayablesDueToThirdParties': 'payables_to_third_parties',
        'TradeAndOtherPayablesDueToRelatedParties': 'payables_to_related_parties',
        'DeferredIncome': 'deferred_income',
        'OtherPayables': 'other_payables',
        'TradeAndOtherPayables': 'total_trade_and_other_payables'
    }

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.errors = {}
        self.taxonomy_version = self._get_taxonomy_version()
        
    def _get_taxonomy_version(self) -> str:
        """Get the taxonomy version from the data or default to latest"""
        filing_info = None
        for name in ['FilingInformation', 'filing_information']:
            if name in self.data:
                filing_info = self.data.get(name, {})
                break
                
        version = None
        if filing_info:
            version = filing_info.get('TaxonomyVersion', filing_info.get('taxonomy_version'))
        
        # Only support 2022 versions
        valid_versions = {'2022', '2022.2'}
        if version in valid_versions:
            return version
            
        return '2022.2'  # Default to latest 2022 version
        
    def _get_mapped_value(self, data: Dict[str, Any], mapping: Dict[str, str], key: str) -> Any:
        """Get value using field mapping"""
        mapped_key = mapping.get(key)
        if mapped_key and key in data:
            return data[key]
        return None

    def _validate_section_with_mapping(self, section_data: Dict[str, Any], mapping: Dict[str, str], section_name: str) -> None:
        """Validate a section using field mapping"""
        if not section_data:
            return

        for json_field, model_field in mapping.items():
            value = section_data.get(json_field)
            if value is None and not self._is_optional_field(model_field):
                self._add_error(section_name, f"Required field '{json_field}' is missing")

    def _is_optional_field(self, field_name: str) -> bool:
        """Check if a field is optional based on model definitions"""
        optional_fields = {
            'prior_period_start',
            'parent_entity_name',
            'ultimate_parent_name',
            'treasury_shares',
            'other_reserves',
            'noncontrolling_interests'
        }
        return field_name in optional_fields

    def validate(self) -> Tuple[bool, Dict[str, List[str]]]:
        """Validate XBRL data using field mappings"""
        try:
            # Reset errors
            self.errors = {}

            # Validate each section using mappings
            if 'FilingInformation' in self.data:
                self._validate_section_with_mapping(
                    self.data['FilingInformation'],
                    self.FILING_INFO_MAPPING,
                    'FilingInformation'
                )

            if 'StatementOfFinancialPosition' in self.data:
                sfp = self.data['StatementOfFinancialPosition']
                if 'CurrentAssets' in sfp:
                    self._validate_section_with_mapping(
                        sfp['CurrentAssets'],
                        self.CURRENT_ASSETS_MAPPING,
                        'CurrentAssets'
                    )
                if 'NonCurrentAssets' in sfp:
                    self._validate_section_with_mapping(
                        sfp['NonCurrentAssets'],
                        self.NONCURRENT_ASSETS_MAPPING,
                        'NonCurrentAssets'
                    )

            if 'IncomeStatement' in self.data:
                self._validate_section_with_mapping(
                    self.data['IncomeStatement'],
                    self.INCOME_STATEMENT_MAPPING,
                    'IncomeStatement'
                )

            if 'Notes' in self.data:
                notes = self.data['Notes']
                if 'TradeAndOtherReceivables' in notes:
                    self._validate_section_with_mapping(
                        notes['TradeAndOtherReceivables'],
                        self.NOTES_RECEIVABLES_MAPPING,
                        'Notes.TradeAndOtherReceivables'
                    )
                if 'TradeAndOtherPayables' in notes:
                    self._validate_section_with_mapping(
                        notes['TradeAndOtherPayables'],
                        self.NOTES_PAYABLES_MAPPING,
                        'Notes.TradeAndOtherPayables'
                    )

            # Validate cross-statement consistency
            self._validate_cross_statement_consistency()

        except Exception as e:
            logger.error(f"Unexpected error during validation: {str(e)}", exc_info=True)
            self._add_error('general', f"Validation error: {str(e)}")

        return len(self.errors) == 0, self.errors
    
    def _validate_cross_statement_consistency(self) -> None:
        """Validate consistency across different sections"""
        try:
            # Check if total assets equals the sum of current and non-current assets
            sfp_key = next((k for k in ['StatementOfFinancialPosition', 'statement_of_financial_position'] if k in self.data), None)
            if sfp_key:
                financial_position = self.data.get(sfp_key, {})
                
                # Get total assets
                total_assets = 0
                total_assets_key = next((k for k in ['Assets', 'assets', 'total_assets'] if k in financial_position), None)
                if total_assets_key and financial_position.get(total_assets_key) is not None:
                    total_assets = Decimal(str(financial_position.get(total_assets_key, 0)))
                
                # Get current assets
                current_assets = 0
                current_assets_key = next((k for k in ['CurrentAssets', 'current_assets'] if k in financial_position), None)
                if current_assets_key:
                    current_assets_section = financial_position.get(current_assets_key, {})
                    total_current_assets_key = next((k for k in ['CurrentAssets', 'current_assets', 'total_current_assets'] 
                                                if k in current_assets_section), None)
                    if total_current_assets_key and current_assets_section.get(total_current_assets_key) is not None:
                        current_assets = Decimal(str(current_assets_section.get(total_current_assets_key, 0)))
                
                # Get non-current assets
                non_current_assets = 0
                non_current_assets_key = next((k for k in ['NonCurrentAssets', 'NoncurrentAssets', 'non_current_assets', 'noncurrent_assets'] 
                                          if k in financial_position), None)
                if non_current_assets_key:
                    non_current_assets_section = financial_position.get(non_current_assets_key, {})
                    total_non_current_assets_key = next((k for k in ['NonCurrentAssets', 'NoncurrentAssets', 'non_current_assets', 
                                                               'noncurrent_assets', 'total_non_current_assets', 'total_noncurrent_assets'] 
                                                   if k in non_current_assets_section), None)
                    if total_non_current_assets_key and non_current_assets_section.get(total_non_current_assets_key) is not None:
                        non_current_assets = Decimal(str(non_current_assets_section.get(total_non_current_assets_key, 0)))
                
                # Determine rounding tolerance
                filing_info_key = next((k for k in ['FilingInformation', 'filing_information'] if k in self.data), None)
                rounding_tolerance = Decimal('0.1')  # Default tolerance
                
                if filing_info_key:
                    filing_info = self.data.get(filing_info_key, {})
                    rounding_field = next((k for k in ['LevelOfRoundingUsedInFinancialStatements', 
                                                    'level_of_rounding_used_in_financial_statements'] if k in filing_info), None)
                    if rounding_field:
                        rounding = filing_info.get(rounding_field)
                        if rounding == 'Thousands':
                            rounding_tolerance = Decimal('1')
                        elif rounding == 'Millions':
                            rounding_tolerance = Decimal('0.1') * Decimal('1000')
                        elif rounding == 'Billions':
                            rounding_tolerance = Decimal('0.1') * Decimal('1000000')
                
                # Check if assets equals current assets + non-current assets
                calculated_total = current_assets + non_current_assets
                if abs(calculated_total - total_assets) > rounding_tolerance:
                    self._add_error('StatementOfFinancialPosition', 
                                f'Total assets ({total_assets}) does not equal the sum of current assets ' 
                                f'({current_assets}) and non-current assets ({non_current_assets})')
                
                # Check accounting equation: Assets = Liabilities + Equity
                total_liabilities = 0
                liabilities_key = next((k for k in ['Liabilities', 'liabilities', 'total_liabilities'] if k in financial_position), None)
                if liabilities_key and financial_position.get(liabilities_key) is not None:
                    total_liabilities = Decimal(str(financial_position.get(liabilities_key, 0)))
                
                total_equity = 0
                equity_key = next((k for k in ['Equity', 'equity'] if k in financial_position), None)
                if equity_key:
                    equity_section = financial_position.get(equity_key, {})
                    equity_total_key = next((k for k in ['Equity', 'equity', 'total_equity'] if k in equity_section), None)
                    if equity_total_key and equity_section.get(equity_total_key) is not None:
                        total_equity = Decimal(str(equity_section.get(equity_total_key, 0)))
                    elif equity_section.get('Equity') is not None:
                        total_equity = Decimal(str(equity_section.get('Equity', 0)))
                
                if abs((total_liabilities + total_equity) - total_assets) > rounding_tolerance:
                    self._add_error('StatementOfFinancialPosition', 
                                f'Assets ({total_assets}) must equal Liabilities ({total_liabilities}) plus Equity ({total_equity})')
                
        except Exception as e:
            logger.error(f"Error in cross statement consistency validation: {str(e)}", exc_info=True)
            self._add_error('general', f"Error validating cross statement consistency: {str(e)}")
    
    def _add_error(self, section: str, message: str) -> None:
        """Add an error message to the specified section"""
        if section not in self.errors:
            self.errors[section] = []
        self.errors[section].append(message)
        logger.debug(f"Added validation error - {section}: {message}")