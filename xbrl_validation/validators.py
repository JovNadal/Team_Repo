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
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.errors = {}
        # Determine which taxonomy version to use
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
        
    def validate(self) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Validate the XBRL data according to ACRA rules
        Returns:
            Tuple containing:
            - Boolean indicating if validation passed
            - Dictionary of errors by section
        """
        # Reset errors
        self.errors = {}
        
        try:
            # Check required sections
            self._validate_required_sections()
            
            # Validate filing information
            filing_info_key = next((k for k in ['FilingInformation', 'filing_information'] if k in self.data), None)
            if filing_info_key:
                self._validate_filing_information()
                
            # Validate financial statements
            sfp_key = next((k for k in ['StatementOfFinancialPosition', 'statement_of_financial_position'] if k in self.data), None)
            if sfp_key:
                self._validate_financial_position()
                
            is_key = next((k for k in ['IncomeStatement', 'income_statement'] if k in self.data), None)
            if is_key:
                self._validate_income_statement()
                
            scf_key = next((k for k in ['StatementOfCashFlows', 'statement_of_cash_flows'] if k in self.data), None)
            if scf_key:
                self._validate_cash_flows()
                
            scie_key = next((k for k in ['StatementOfChangesInEquity', 'statement_of_changes_in_equity'] if k in self.data), None)
            if scie_key:
                self._validate_changes_in_equity()
                
            # Validate notes
            notes_key = next((k for k in ['Notes', 'notes'] if k in self.data), None)
            if notes_key:
                self._validate_notes()
                
            # Validate directors statement
            ds_key = next((k for k in ['DirectorsStatement', 'directors_statement'] if k in self.data), None)
            if ds_key:
                self._validate_directors_statement()
                
            # Validate audit report
            ar_key = next((k for k in ['AuditReport', 'audit_report'] if k in self.data), None)
            if ar_key:
                self._validate_audit_report()
                
            # Check cross-statement consistency
            self._validate_cross_statement_consistency()
            
            # Validate data formatting
            self._validate_data_formatting()
            
        except Exception as e:
            logger.error(f"Unexpected error during validation: {str(e)}", exc_info=True)
            self._add_error('general', f"Validation error: {str(e)}")
        
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
    
    def _validate_filing_information(self) -> None:
        """Validate filing information according to ACRA rules"""
        filing_info = self.data.get('FilingInformation', {})
        
        # Map incoming field names to expected field names
        field_mapping = {
            'company_name': ['company_name', 'NameOfCompany'],
            'unique_entity_number': ['unique_entity_number', 'UniqueEntityNumber'],
            'current_period_start': ['current_period_start', 'CurrentPeriodStartDate'],
            'current_period_end': ['current_period_end', 'CurrentPeriodEndDate'],
            'xbrl_filing_type': ['xbrl_filing_type', 'TypeOfXBRLFiling'],
            'financial_statement_type': ['financial_statement_type', 'NatureOfFinancialStatementsCompanyLevelOrConsolidated']
        }
        
        # Required fields with validation functions
        required_validations = {
            'company_name': self._validate_non_empty,
            'unique_entity_number': self._validate_uen,
            'current_period_start': self._validate_date,
            'current_period_end': self._validate_date,
            'xbrl_filing_type': self._validate_filing_type,
            'financial_statement_type': self._validate_statement_type
        }
        
        # Check each required field
        for expected_field, validator in required_validations.items():
            # Try all possible field names
            field_value = None
            field_found = False
            
            for field_name in field_mapping.get(expected_field, [expected_field]):
                if field_name in filing_info:
                    field_value = filing_info.get(field_name)
                    field_found = True
                    break
            
            if not field_found:
                self._add_error('FilingInformation', f"Missing required field: {expected_field}")
            else:
                result = validator(field_value)
                if result:
                    self._add_error('FilingInformation', f"{expected_field}: {result}")
    
    def _validate_financial_position(self) -> None:
        """Validate statement of financial position according to ACRA rules"""
        sfp_key = next((k for k in ['StatementOfFinancialPosition', 'statement_of_financial_position'] if k in self.data), None)
        if not sfp_key:
            return
            
        financial_position = self.data.get(sfp_key, {})
        
        # Get current assets
        current_assets_key = next((k for k in ['CurrentAssets', 'current_assets'] if k in financial_position), None)
        if current_assets_key:
            current_assets = financial_position.get(current_assets_key, {})
            
            # Check for total current assets
            total_current_assets = 0
            total_current_assets_key = next((k for k in ['CurrentAssets', 'current_assets', 'total_current_assets'] 
                                            if k in current_assets), None)
            if total_current_assets_key and current_assets.get(total_current_assets_key) is not None:
                total_current_assets = Decimal(str(current_assets.get(total_current_assets_key, 0)))
        else:
            total_current_assets = 0
        
        # Get non-current assets
        noncurrent_assets_key = next((k for k in ['NonCurrentAssets', 'non_current_assets', 'noncurrent_assets'] 
                                    if k in financial_position), None)
        if noncurrent_assets_key:
            noncurrent_assets = financial_position.get(noncurrent_assets_key, {})
            
            # Check for total non-current assets
            total_noncurrent_assets = 0
            total_noncurrent_assets_key = next((k for k in ['NonCurrentAssets', 'non_current_assets', 'noncurrent_assets', 
                                                          'total_noncurrent_assets', 'total_non_current_assets'] 
                                              if k in noncurrent_assets), None)
            if total_noncurrent_assets_key and noncurrent_assets.get(total_noncurrent_assets_key) is not None:
                total_noncurrent_assets = Decimal(str(noncurrent_assets.get(total_noncurrent_assets_key, 0)))
        else:
            total_noncurrent_assets = 0
        
        # Get total assets
        total_assets = 0
        total_assets_key = next((k for k in ['Assets', 'assets', 'total_assets'] if k in financial_position), None)
        if total_assets_key and financial_position.get(total_assets_key) is not None:
            total_assets = Decimal(str(financial_position.get(total_assets_key, 0)))
        
        # Check if totals match (with small tolerance for rounding)
        calculated_total_assets = total_current_assets + total_noncurrent_assets
        
        # Determine rounding tolerance based on the level of rounding in the financial statements
        filing_info_key = next((k for k in ['FilingInformation', 'filing_information'] if k in self.data), None)
        rounding_tolerance = Decimal('0.1')  # Default tolerance
        
        if filing_info_key:
            filing_info = self.data.get(filing_info_key, {})
            rounding_field = next((k for k in ['LevelOfRoundingUsedInFinancialStatements', 'level_of_rounding_used_in_financial_statements'] 
                                 if k in filing_info), None)
            if rounding_field:
                rounding = filing_info.get(rounding_field)
                if rounding == 'Thousands':
                    rounding_tolerance = Decimal('1')
                elif rounding == 'Millions':
                    rounding_tolerance = Decimal('0.1') * Decimal('1000')
                elif rounding == 'Billions':
                    rounding_tolerance = Decimal('0.1') * Decimal('1000000')
        
        if abs(calculated_total_assets - total_assets) > rounding_tolerance:
            self._add_error('StatementOfFinancialPosition', 
                        f'Total assets ({total_assets}) does not equal the sum of current assets ' 
                           f'({total_current_assets}) and non-current assets ({total_noncurrent_assets})')
        
        # Check for liabilities and equity
        total_liabilities = 0
        liabilities_key = next((k for k in ['Liabilities', 'liabilities', 'total_liabilities'] if k in financial_position), None)
        if liabilities_key and financial_position.get(liabilities_key) is not None:
            total_liabilities = Decimal(str(financial_position.get(liabilities_key, 0)))
        
        total_equity = 0
        equity_key = next((k for k in ['Equity', 'equity'] if k in financial_position), None)
        if equity_key:
            equity = financial_position.get(equity_key, {})
            equity_total_key = next((k for k in ['Equity', 'equity', 'total_equity'] if k in equity), None)
            if equity_total_key and equity.get(equity_total_key) is not None:
                total_equity = Decimal(str(equity.get(equity_total_key, 0)))
        
        if abs((total_liabilities + total_equity) - total_assets) > rounding_tolerance:
            self._add_error('StatementOfFinancialPosition', 
                        f'Assets ({total_assets}) must equal Liabilities ({total_liabilities}) plus Equity ({total_equity})')
    
    def _validate_income_statement(self) -> None:
        """Validate income statement according to ACRA rules"""
        income_statement = self.data.get('income_statement', {})
        
        # Make sure revenue is present when profit exists
        has_profit = 'profit_loss' in income_statement and income_statement['profit_loss'] != 0
        has_revenue = 'revenue' in income_statement and income_statement['revenue'] != 0
        
        if has_profit and not has_revenue:
            self._add_error('income_statement', 'Revenue should be reported when profit exists')
        
        # Profit/Loss calculation check
        if 'profit_loss' in income_statement:
            reported_profit = Decimal(str(income_statement.get('profit_loss', 0)))
            reported_revenue = Decimal(str(income_statement.get('revenue', 0)))
            reported_expenses = Decimal(str(income_statement.get('total_expenses', 0)))
            
            # Simple check: profit = revenue - expenses
            calculated_profit = reported_revenue - reported_expenses
            
            if 'other_income' in income_statement:
                calculated_profit += Decimal(str(income_statement.get('other_income', 0)))
                
            if abs(calculated_profit - reported_profit) > Decimal('0.1'):
                self._add_error('income_statement', 
                               f'Profit/Loss ({reported_profit}) does not match calculation from revenue and expenses')

    def _validate_cash_flows(self) -> None:
        """Validate statement of cash flows according to ACRA rules"""
        cash_flows = self.data.get('statement_of_cash_flows', {})
        
        # Check if opening + net change = closing cash and cash equivalents
        opening_cash = Decimal(str(cash_flows.get('cash_and_cash_equivalents_beginning_period', 0)))
        net_increase = Decimal(str(cash_flows.get('net_increase_decrease_in_cash_and_cash_equivalents', 0)))
        closing_cash = Decimal(str(cash_flows.get('cash_and_cash_equivalents_end_period', 0)))
        
        calculated_closing_cash = opening_cash + net_increase
        
        if abs(calculated_closing_cash - closing_cash) > Decimal('0.1'):
            self._add_error('statement_of_cash_flows', 
                           f'Closing cash ({closing_cash}) does not equal opening cash ({opening_cash}) plus net change ({net_increase})')
        
        # Check if net cash flow equals sum of operating, investing and financing activities
        operating_cash = Decimal(str(cash_flows.get('net_cash_flows_from_used_in_operating_activities', 0)))
        investing_cash = Decimal(str(cash_flows.get('net_cash_flows_from_used_in_investing_activities', 0)))
        financing_cash = Decimal(str(cash_flows.get('net_cash_flows_from_used_in_financing_activities', 0)))
        
        calculated_net_cash = operating_cash + investing_cash + financing_cash
        
        # Allow for rounding differences or effects of exchange rate changes
        if abs(calculated_net_cash - net_increase) > Decimal('0.5'):
            # Check if there's an exchange rate effect
            exchange_effect = Decimal(str(cash_flows.get('effect_of_exchange_rate_changes_on_cash_and_cash_equivalents', 0)))
            if abs((calculated_net_cash + exchange_effect) - net_increase) > Decimal('0.1'):
                self._add_error('statement_of_cash_flows', 
                              f'Net increase in cash ({net_increase}) does not equal sum of operating ({operating_cash}), '
                              f'investing ({investing_cash}), and financing ({financing_cash}) activities')
    
    def _validate_changes_in_equity(self) -> None:
        """Validate statement of changes in equity according to ACRA rules"""
        changes_in_equity = self.data.get('statement_of_changes_in_equity', {})
        
        # Check if opening + total changes = closing equity
        opening_equity = Decimal(str(changes_in_equity.get('total_equity_beginning_period', 0)))
        total_changes = Decimal(str(changes_in_equity.get('total_changes_in_equity', 0)))
        closing_equity = Decimal(str(changes_in_equity.get('total_equity_end_period', 0)))
        
        calculated_closing_equity = opening_equity + total_changes
        
        if abs(calculated_closing_equity - closing_equity) > Decimal('0.1'):
            self._add_error('statement_of_changes_in_equity', 
                           f'Closing equity ({closing_equity}) does not equal opening equity ({opening_equity}) '
                           f'plus total changes ({total_changes})')
        
        # Check consistency with profit/loss in income statement
        if 'profit_loss_attributable_to_owners' in changes_in_equity and 'income_statement' in self.data:
            equity_profit = Decimal(str(changes_in_equity.get('profit_loss_attributable_to_owners', 0)))
            income_profit = Decimal(str(self.data['income_statement'].get('profit_loss', 0)))
            
            # Only validate if both values are non-zero (might not be reported in both statements)
            if equity_profit != 0 and income_profit != 0:
                if abs(equity_profit - income_profit) > Decimal('0.1'):
                    self._add_error('statement_of_changes_in_equity', 
                                  f'Profit/loss in statement of changes in equity ({equity_profit}) does not match '
                                  f'profit/loss in income statement ({income_profit})')
    
    def _validate_notes(self) -> None:
        """Validate notes section according to ACRA rules"""
        notes_key = next((k for k in ['Notes', 'notes'] if k in self.data), None)
        if not notes_key:
            return
            
        notes = self.data.get(notes_key, {})
        
        # Check consistency between notes and financial statements
        
        # 1. Trade and Other Receivables
        sfp_key = next((k for k in ['StatementOfFinancialPosition', 'statement_of_financial_position'] if k in self.data), None)
        if sfp_key:
            financial_position = self.data.get(sfp_key, {})
            
            receivables_notes_key = next((k for k in ['TradeAndOtherReceivables', 'trade_and_other_receivables'] if k in notes), None)
            if receivables_notes_key:
                receivables_notes = notes.get(receivables_notes_key, {})
                notes_total_key = next((k for k in ['TradeAndOtherReceivables', 'trade_and_other_receivables'] if k in receivables_notes), None)
                
                if notes_total_key and receivables_notes.get(notes_total_key) is not None:
                    notes_total = Decimal(str(receivables_notes.get(notes_total_key, 0)))
                    
                    # Find receivables in the statement of financial position
                    current_assets_key = next((k for k in ['CurrentAssets', 'current_assets'] if k in financial_position), None)
                    if current_assets_key:
                        current_assets = financial_position.get(current_assets_key, {})
                        receivables_sfp_key = next((k for k in ['TradeAndOtherReceivablesCurrent', 'trade_and_other_receivables_current', 
                                                            'trade_and_other_receivables'] if k in current_assets), None)
                        
                        # Check if the key exists and the value is not None
                        if receivables_sfp_key and current_assets.get(receivables_sfp_key) is not None:
                            statement_total = Decimal(str(current_assets.get(receivables_sfp_key, 0)))
                            
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
                            
                            if abs(notes_total - statement_total) > rounding_tolerance:
                                self._add_error('Notes', 
                               f'Trade and other receivables in notes ({notes_total}) does not match ' 
                               f'the value in statement of financial position ({statement_total})')
    
        # 2. Check for null values in required fields
        # Trade and Other Payables
        current_liabilities_key = next((k for k in ['CurrentLiabilities', 'current_liabilities'] 
                                    if k in financial_position), None)
        if current_liabilities_key:
            current_liabilities = financial_position.get(current_liabilities_key, {})
            payables_key = next((k for k in ['TradeAndOtherPayablesCurrent', 'trade_and_other_payables_current'] 
                              if k in current_liabilities), None)
            
            # If key exists but value is null
            if payables_key and current_liabilities.get(payables_key) is None:
                self._add_error('StatementOfFinancialPosition.CurrentLiabilities', 
                             'TradeAndOtherPayablesCurrent should not be null')
        
        # Non-current Trade and Other Payables
        noncurrent_liabilities_key = next((k for k in ['NonCurrentLiabilities', 'non_current_liabilities'] 
                                       if k in financial_position), None)
        if noncurrent_liabilities_key:
            noncurrent_liabilities = financial_position.get(noncurrent_liabilities_key, {})
            payables_key = next((k for k in ['TradeAndOtherPayablesNoncurrent', 'trade_and_other_payables_noncurrent'] 
                              if k in noncurrent_liabilities), None)
            
            # If key exists but value is null
            if payables_key and noncurrent_liabilities.get(payables_key) is None:
                self._add_error('StatementOfFinancialPosition.NonCurrentLiabilities', 
                             'TradeAndOtherPayablesNoncurrent should not be null')

    def _validate_directors_statement(self) -> None:
        """Validate directors statement according to ACRA rules"""
        ds_key = next((k for k in ['DirectorsStatement', 'directors_statement'] if k in self.data), None)
        if not ds_key:
            return
            
        directors_statement = self.data.get(ds_key, {})
        
        # Check required fields for Directors Statement
        required_fields = [
            'WhetherInDirectorsOpinionFinancialStatementsAreDrawnUpSoAsToExhibitATrueAndFairView',
            'WhetherThereAreReasonableGroundsToBelieveThatCompanyWillBeAbleToPayItsDebtsAsAndWhenTheyFallDueAtDateOfStatement'
        ]
        
        for field in required_fields:
            snake_case = self._convert_to_snake_case(field)
            if field not in directors_statement and snake_case not in directors_statement:
                self._add_error('DirectorsStatement', f"Missing required field: {field}")
            elif (field in directors_statement and directors_statement[field] is None) or \
                 (snake_case in directors_statement and directors_statement[snake_case] is None):
                self._add_error('DirectorsStatement', f"Field {field} must not be null")
    
    def _validate_audit_report(self) -> None:
        """Validate audit report according to ACRA rules"""
        ar_key = next((k for k in ['AuditReport', 'audit_report'] if k in self.data), None)
        if not ar_key:
            return
            
        audit_report = self.data.get(ar_key, {})
        
        # Check audit opinion type
        opinion_field = 'TypeOfAuditOpinionInIndependentAuditorsReport'
        snake_opinion = self._convert_to_snake_case(opinion_field)
        
        opinion = None
        if opinion_field in audit_report:
            opinion = audit_report[opinion_field]
        elif snake_opinion in audit_report:
            opinion = audit_report[snake_opinion]
            
        if opinion:
            valid_opinions = {'Unqualified', 'Qualified', 'Adverse', 'Disclaimer'}
            if opinion not in valid_opinions:
                self._add_error('AuditReport', f"Invalid audit opinion: {opinion}. Must be one of {', '.join(valid_opinions)}")
    
    def _validate_data_formatting(self) -> None:
        """Validate data formatting according to ACRA rules"""
        filing_info_key = next((k for k in ['FilingInformation', 'filing_information'] if k in self.data), None)
        if not filing_info_key:
            return
            
        filing_info = self.data.get(filing_info_key, {})
        
        # Check currency consistency
        currency_field = 'DescriptionOfPresentationCurrency'
        snake_currency = self._convert_to_snake_case(currency_field)
        
        currency = None
        if currency_field in filing_info:
            currency = filing_info[currency_field]
        elif snake_currency in filing_info:
            currency = filing_info[snake_currency]
            
        if currency and currency not in {'SGD', 'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'HKD', 'AUD', 'INR', 'MYR'}:
            self._add_error('FilingInformation', f"Invalid presentation currency: {currency}")
        
        # Check rounding level
        rounding_field = 'LevelOfRoundingUsedInFinancialStatements'
        snake_rounding = self._convert_to_snake_case(rounding_field)
        
        rounding = None
        if rounding_field in filing_info:
            rounding = filing_info[rounding_field]
        elif snake_rounding in filing_info:
            rounding = filing_info[snake_rounding]
            
        if rounding and rounding not in {'Units', 'Thousands', 'Millions', 'Billions'}:
            self._add_error('FilingInformation', f"Invalid rounding level: {rounding}. Must be one of Units, Thousands, Millions, Billions")
    
    def _convert_to_snake_case(self, camel_case: str) -> str:
        """Convert a camel case string to snake case"""
        # For example, convert "DescriptionOfPresentationCurrency" to "description_of_presentation_currency"
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_case)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    def _add_error(self, section: str, message: str) -> None:
        """Add an error message to the specified section"""
        if section not in self.errors:
            self.errors[section] = []
        self.errors[section].append(message)
        logger.debug(f"Added validation error - {section}: {message}")
    
    def _validate_non_empty(self, value: Any) -> Optional[str]:
        """Validate that a value is not empty"""
        if not value:
            return "Value cannot be empty"
        return None
        
    def _validate_uen(self, uen: str) -> Optional[str]:
        """Validate Singapore UEN format"""
        if not uen:
            return "UEN is required"
            
        # Business registered with ACRA (e.g., 53333444A)
        business_pattern = r'^\d{8}[A-Z]$'
        
        # Local company (e.g., 201912345D)
        local_company_pattern = r'^(19|20)\d{2}\d{5}[A-Z]$'
        
        # Other entities registered with ACRA (e.g., T13LL1234J, S98LL1234J, R99LL1234J)
        other_entity_pattern = r'^[TSR]\d{2}[A-Z]{2}\d{4}[A-Z]$'
        
        if not (re.match(business_pattern, uen) or 
                re.match(local_company_pattern, uen) or 
                re.match(other_entity_pattern, uen)):
            return "Invalid UEN format"
            
        return None
        
    def _validate_date(self, date: str) -> Optional[str]:
        """Validate date format (YYYY-MM-DD)"""
        if not date:
            return "Date is required"
            
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        if not re.match(date_pattern, date):
            return "Invalid date format (should be YYYY-MM-DD)"
            
        return None
        
    def _validate_filing_type(self, filing_type: str) -> Optional[str]:
        """Validate XBRL filing type"""
        if not filing_type:
            return "Filing type is required"
            
        valid_types = {'Full', 'Partial'}
        normalized_type = filing_type.strip().title()
        
        if normalized_type not in valid_types:
            return f"Invalid filing type (should be one of: {', '.join(valid_types)})"
            
        return None
        
    def _validate_statement_type(self, stmt_type: str) -> Optional[str]:
        """Validate financial statement type"""
        if not stmt_type:
            return "Statement type is required"
            
        valid_types = {'Company', 'Consolidated'}
        normalized_type = stmt_type.strip().title()
        
        if normalized_type not in valid_types:
            return f"Invalid statement type (should be one of: {', '.join(valid_types)})"
            
        return None

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