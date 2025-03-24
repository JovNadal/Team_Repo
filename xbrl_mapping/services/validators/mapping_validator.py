from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import logging
import re
from datetime import datetime

@dataclass
class ValidationResult:
    """Results of XBRL data validation"""
    is_valid: bool
    errors: List[Dict[str, Any]] = field(default_factory=list)


class XBRLValidator:
    """
    Validates XBRL financial data structure.
    
    Performs basic validation to ensure data fields exist and have valid types.
    Does not perform complex business rule validation.
    """
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Perform basic validation on XBRL data
        
        Args:
            data: Dictionary containing the XBRL data to validate
            
        Returns:
            ValidationResult with validation status and any errors
        """
        errors = []
        
        # Verify data is a dictionary and not empty
        if not data or not isinstance(data, dict):
            return ValidationResult(
                is_valid=False, 
                errors=[{'section': 'root', 'message': 'Data must be a non-empty dictionary'}]
            )
        
        # 1. Check for required top-level sections
        required_sections = ['filingInformation', 'statementOfFinancialPosition', 'incomeStatement']
        for section in required_sections:
            if section not in data:
                errors.append({
                    'section': 'structure',
                    'message': f"Missing required section: {section}"
                })
        
        # 2. Validate filingInformation
        if 'filingInformation' in data:
            filing_info = data['filingInformation']
            if not isinstance(filing_info, dict):
                errors.append({
                    'section': 'filingInformation',
                    'message': "Filing information must be an object"
                })
            else:
                # Check required fields exist
                required_fields = ['NameOfCompany', 'UniqueEntityNumber', 'CurrentPeriodStartDate', 'CurrentPeriodEndDate']
                for field in required_fields:
                    if field not in filing_info or not filing_info[field]:
                        errors.append({
                            'section': 'filingInformation',
                            'message': f"Missing required field: {field}"
                        })
                
                # Validate date fields have valid format (basic check)
                date_fields = ['CurrentPeriodStartDate', 'CurrentPeriodEndDate']
                for field in date_fields:
                    if field in filing_info and filing_info[field]:
                        if not self._validate_date(filing_info[field]):
                            errors.append({
                                'section': 'filingInformation',
                                'message': f"Field {field} must be a valid date in YYYY-MM-DD format"
                            })
        
        # 3. Validate statementOfFinancialPosition
        if 'statementOfFinancialPosition' in data:
            sof_data = data['statementOfFinancialPosition']
            if not isinstance(sof_data, dict):
                errors.append({
                    'section': 'statementOfFinancialPosition',
                    'message': "Statement of financial position must be an object"
                })
            else:
                # Check required components exist
                required_components = ['currentAssets', 'nonCurrentAssets', 'currentLiabilities', 'nonCurrentLiabilities', 'equity']
                for component in required_components:
                    if component not in sof_data:
                        errors.append({
                            'section': 'statementOfFinancialPosition',
                            'message': f"Missing required component: {component}"
                        })
                
                # Validate numeric fields
                numeric_fields = ['Assets', 'Liabilities']
                for field in numeric_fields:
                    if field in sof_data and not self._is_numeric(sof_data[field]):
                        errors.append({
                            'section': 'statementOfFinancialPosition',
                            'message': f"Field {field} must be a number"
                        })
        
        # 4. Validate incomeStatement
        if 'incomeStatement' in data:
            income_data = data['incomeStatement']
            if not isinstance(income_data, dict):
                errors.append({
                    'section': 'incomeStatement',
                    'message': "Income statement must be an object"
                })
            else:
                # Check required fields exist
                required_fields = ['Revenue', 'ProfitLoss']
                for field in required_fields:
                    if field not in income_data:
                        errors.append({
                            'section': 'incomeStatement',
                            'message': f"Missing required field: {field}"
                        })
                
                # Validate numeric fields
                numeric_fields = ['Revenue', 'ProfitLoss', 'ProfitLossBeforeTaxation']
                for field in numeric_fields:
                    if field in income_data and not self._is_numeric(income_data[field]):
                        errors.append({
                            'section': 'incomeStatement',
                            'message': f"Field {field} must be a number"
                        })
        
        # Return validation result
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
    
    def _is_numeric(self, value) -> bool:
        """
        Check if a value is numeric (int, float, or numeric string)
        
        Args:
            value: The value to check
            
        Returns:
            bool: True if value is numeric, False otherwise
        """
        if value is None:
            return False
            
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _validate_date(self, date_str: str) -> bool:
        """
        Basic validation for date string format (YYYY-MM-DD)
        
        Args:
            date_str: The date string to validate
            
        Returns:
            bool: True if date string has valid format, False otherwise
        """
        if not date_str or not isinstance(date_str, str):
            return False
            
        # Simple pattern matching for YYYY-MM-DD format
        pattern = r'^\d{4}-\d{2}-\d{2}$'
        return bool(re.match(pattern, date_str))
    
    def _validate_uen(self, uen: str) -> bool:
        """
        Simple validation for UEN existence
        
        Args:
            uen: The UEN to validate
            
        Returns:
            bool: True if UEN exists and is a string, False otherwise
        """
        return bool(uen and isinstance(uen, str))
    
    def _validate_accounting_equation(self, assets, liabilities, equity) -> bool:
        """
        Simple validation that assets, liabilities and equity are numeric
        
        Args:
            assets: The assets value
            liabilities: The liabilities value
            equity: The equity value
            
        Returns:
            bool: True if all values are numeric, False otherwise
        """
        return all(self._is_numeric(val) for val in [assets, liabilities, equity])
    
    def _validate_profit_attribution(self, profit, owners_profit, nci_profit) -> bool:
        """
        Simple validation that profit values are numeric
        
        Args:
            profit: Total profit/loss value
            owners_profit: Owners' profit value
            nci_profit: Non-controlling interest profit value
            
        Returns:
            bool: True if all values are numeric, False otherwise
        """
        return all(self._is_numeric(val) for val in [profit, owners_profit, nci_profit if nci_profit is not None else 0])