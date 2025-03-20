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
        required_sections = {'filing_information'}
        
        missing_sections = required_sections - set(self.data.keys())
        if missing_sections:
            self.errors['structure'] = [f"Missing required section(s): {', '.join(missing_sections)}"]


class ACRAXBRLValidator:
    """ACRA-specific XBRL validation rules"""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.errors = {}
        # Determine which taxonomy version to use
        self.taxonomy_version = self._get_taxonomy_version()
        
    def _get_taxonomy_version(self) -> str:
        """Get the taxonomy version from the data or default to latest"""
        filing_info = self.data.get('filing_information', {})
        version = filing_info.get('taxonomy_version')
        
        valid_versions = {'2016', '2020', '2022.2'}
        if version in valid_versions:
            return version
            
        return '2022.2'  # Default to latest
        
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
            if 'filing_information' in self.data:
                self._validate_filing_information()
                
            # Validate financial statements
            if 'statement_of_financial_position' in self.data:
                self._validate_financial_position()
                
            if 'income_statement' in self.data:
                self._validate_income_statement()
                
            if 'statement_of_cash_flows' in self.data:
                self._validate_cash_flows()
                
            if 'statement_of_changes_in_equity' in self.data:
                self._validate_changes_in_equity()
                
            # Validate notes
            if 'notes' in self.data:
                self._validate_notes()
                
            # Check cross-statement consistency
            self._validate_cross_statement_consistency()
            
        except Exception as e:
            logger.error(f"Unexpected error during validation: {str(e)}", exc_info=True)
            self._add_error('general', f"Validation error: {str(e)}")
        
        return len(self.errors) == 0, self.errors
        
    def _validate_required_sections(self) -> None:
        """Validate that all required sections are present"""
        # ACRA requires these sections for all filings
        required_sections = {
            'filing_information',
            'statement_of_financial_position',
            'income_statement'
        }
        
        missing_sections = required_sections - set(self.data.keys())
        if missing_sections:
            self._add_error('structure', f"Missing required section(s): {', '.join(missing_sections)}")
    
    def _validate_filing_information(self) -> None:
        """Validate filing information according to ACRA rules"""
        filing_info = self.data.get('filing_information', {})
        
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
        for field, validator in required_validations.items():
            if field not in filing_info:
                self._add_error('filing_information', f"Missing required field: {field}")
            else:
                result = validator(filing_info.get(field))
                if result:
                    self._add_error('filing_information', f"{field}: {result}")
    
    def _validate_financial_position(self) -> None:
        """Validate statement of financial position according to ACRA rules"""
        financial_position = self.data.get('statement_of_financial_position', {})
        
        # Check if total assets equals sum of current and non-current assets
        current_assets = financial_position.get('current_assets', {})
        noncurrent_assets = financial_position.get('noncurrent_assets', {})
        
        total_current_assets = Decimal(str(current_assets.get('total_current_assets', 0)))
        total_noncurrent_assets = Decimal(str(noncurrent_assets.get('total_noncurrent_assets', 0)))
        reported_total_assets = Decimal(str(financial_position.get('total_assets', 0)))
        
        calculated_total_assets = total_current_assets + total_noncurrent_assets
        
        # Check if totals match (with small tolerance for rounding)
        if abs(calculated_total_assets - reported_total_assets) > Decimal('0.1'):
            self._add_error('statement_of_financial_position', 
                           f'Total assets ({reported_total_assets}) does not equal the sum of current assets ' 
                           f'({total_current_assets}) and non-current assets ({total_noncurrent_assets})')
        
        # Check if total liabilities equals sum of current and non-current liabilities
        current_liabilities = financial_position.get('current_liabilities', {})
        noncurrent_liabilities = financial_position.get('noncurrent_liabilities', {})
        
        total_current_liabilities = Decimal(str(current_liabilities.get('total_current_liabilities', 0)))
        total_noncurrent_liabilities = Decimal(str(noncurrent_liabilities.get('total_noncurrent_liabilities', 0)))
        reported_total_liabilities = Decimal(str(financial_position.get('total_liabilities', 0)))
        
        calculated_total_liabilities = total_current_liabilities + total_noncurrent_liabilities
        
        if abs(calculated_total_liabilities - reported_total_liabilities) > Decimal('0.1'):
            self._add_error('statement_of_financial_position', 
                           f'Total liabilities ({reported_total_liabilities}) does not equal the sum of current liabilities ' 
                           f'({total_current_liabilities}) and non-current liabilities ({total_noncurrent_liabilities})')
    
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
        notes = self.data.get('notes', {})
        
        # In ACRA, trade and other receivables must match the value in current assets
        if 'trade_and_other_receivables' in notes:
            notes_receivables = notes.get('trade_and_other_receivables', {})
            statement_pos = self.data.get('statement_of_financial_position', {})
            current_assets = statement_pos.get('current_assets', {})
            
            notes_total = Decimal(str(notes_receivables.get('total_trade_and_other_receivables', 0)))
            statement_total = Decimal(str(current_assets.get('trade_and_other_receivables', 0)))
            
            if abs(notes_total - statement_total) > Decimal('0.1'):
                self._add_error('notes', 
                               f'Trade and other receivables in notes ({notes_total}) does not match ' 
                               f'the value in statement of financial position ({statement_total})')
    
    def _validate_cross_statement_consistency(self) -> None:
        """Validate consistency across different sections"""
        # Ensure statement of financial position balances (Assets = Liabilities + Equity)
        if 'statement_of_financial_position' in self.data:
            statement_pos = self.data.get('statement_of_financial_position', {})
            equity = statement_pos.get('equity', {})
            
            total_assets = Decimal(str(statement_pos.get('total_assets', 0)))
            total_liabilities = Decimal(str(statement_pos.get('total_liabilities', 0)))
            total_equity = Decimal(str(equity.get('total_equity', 0)))
            
            # Assets = Liabilities + Equity
            if abs((total_liabilities + total_equity) - total_assets) > Decimal('0.1'):
                self._add_error('cross_section', 
                               f'Assets ({total_assets}) must equal Liabilities ({total_liabilities}) plus Equity ({total_equity})')
                               
        # Check ending equity in statement of financial position matches ending equity in statement of changes in equity
        if 'statement_of_financial_position' in self.data and 'statement_of_changes_in_equity' in self.data:
            statement_pos = self.data.get('statement_of_financial_position', {})
            changes_in_equity = self.data.get('statement_of_changes_in_equity', {})
            
            sfp_equity = Decimal(str(statement_pos.get('equity', {}).get('total_equity', 0)))
            socie_ending_equity = Decimal(str(changes_in_equity.get('total_equity_end_period', 0)))
            
            if abs(sfp_equity - socie_ending_equity) > Decimal('0.1'):
                self._add_error('cross_section', 
                               f'Equity in statement of financial position ({sfp_equity}) does not match ' 
                               f'ending equity in statement of changes in equity ({socie_ending_equity})')
        
        # Check cash and cash equivalents from statement of financial position matches statement of cash flows
        if 'statement_of_financial_position' in self.data and 'statement_of_cash_flows' in self.data:
            statement_pos = self.data.get('statement_of_financial_position', {})
            cash_flows = self.data.get('statement_of_cash_flows', {})
            
            current_assets = statement_pos.get('current_assets', {})
            sfp_cash = Decimal(str(current_assets.get('cash_and_cash_equivalents', 0)))
            scf_ending_cash = Decimal(str(cash_flows.get('cash_and_cash_equivalents_end_period', 0)))
            
            if abs(sfp_cash - scf_ending_cash) > Decimal('0.1'):
                self._add_error('cross_section', 
                               f'Cash and cash equivalents in statement of financial position ({sfp_cash}) does not match ' 
                               f'ending cash in statement of cash flows ({scf_ending_cash})')
    
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
        valid_types = {'Full', 'Partial'}
        if filing_type not in valid_types:
            return f"Invalid filing type (should be one of: {', '.join(valid_types)})"
            
        return None
        
    def _validate_statement_type(self, stmt_type: str) -> Optional[str]:
        """Validate financial statement type"""
        valid_types = {'Company', 'Consolidated'}
        if stmt_type not in valid_types:
            return f"Invalid statement type (should be one of: {', '.join(valid_types)})"
            
        return None