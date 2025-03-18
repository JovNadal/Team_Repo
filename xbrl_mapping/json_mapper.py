import json
from django.core.exceptions import ValidationError
from .models import (
    FilingInformation, DirectorsStatement, AuditReport, 
    CurrentAssets, NonCurrentAssets, CurrentLiabilities, 
    NonCurrentLiabilities, Equity, StatementOfFinancialPosition,
    IncomeStatement, TradeAndOtherReceivables, Notes, PartialXBRL
)

class XBRLJSONMapper:
    """
    Utility class to map JSON data to XBRL models
    """
    
    @staticmethod
    def map_json_to_xbrl(json_data):
        """
        Maps JSON data to XBRL models
        
        Args:
            json_data (dict): The JSON data to map
            
        Returns:
            PartialXBRL: The created XBRL instance
        """
        if isinstance(json_data, str):
            try:
                json_data = json.loads(json_data)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON format")
                
        # Extract data sections
        filing_info_data = json_data.get('filing_information', {})
        directors_statement_data = json_data.get('directors_statement', {})
        audit_report_data = json_data.get('audit_report', {})
        
        financial_position_data = json_data.get('statement_of_financial_position', {})
        current_assets_data = financial_position_data.get('current_assets', {})
        noncurrent_assets_data = financial_position_data.get('noncurrent_assets', {})
        current_liabilities_data = financial_position_data.get('current_liabilities', {})
        noncurrent_liabilities_data = financial_position_data.get('noncurrent_liabilities', {})
        equity_data = financial_position_data.get('equity', {})
        
        income_statement_data = json_data.get('income_statement', {})
        
        notes_data = json_data.get('notes', {})
        trade_receivables_data = notes_data.get('trade_and_other_receivables', {})
        trade_payables_data = notes_data.get('trade_and_other_payables', {})
        
        # Create filing information
        try:
            filing_info = FilingInformation.objects.create(**filing_info_data)
        except ValidationError as e:
            raise ValueError(f"Invalid filing information data: {str(e)}")
        
        # Create directors statement and audit report
        directors_statement = DirectorsStatement.objects.create(
            filing=filing_info, 
            **directors_statement_data
        )
        
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
            total_assets=financial_position_data.get('total_assets', 0),
            total_liabilities=financial_position_data.get('total_liabilities', 0)
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
        
        trade_payables = TradeAndOtherReceivables.objects.create(
            filing=filing_info, 
            **trade_payables_data
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
        
        return xbrl

    @staticmethod
    def export_xbrl_to_json(xbrl_instance):
        """
        Exports an XBRL instance to JSON
        
        Args:
            xbrl_instance (PartialXBRL): The XBRL instance to export
            
        Returns:
            dict: The JSON representation of the XBRL instance
        """
        filing_info = xbrl_instance.filing_information
        result = {
            "filing_information": {
                "company_name": filing_info.company_name,
                "unique_entity_number": filing_info.unique_entity_number,
                "current_period_start": filing_info.current_period_start.isoformat(),
                "current_period_end": filing_info.current_period_end.isoformat(),
                "prior_period_start": filing_info.prior_period_start.isoformat() if filing_info.prior_period_start else None,
                "xbrl_filing_type": filing_info.xbrl_filing_type,
                "financial_statement_type": filing_info.financial_statement_type,
                "accounting_standard": filing_info.accounting_standard,
                "authorisation_date": filing_info.authorisation_date.isoformat(),
                "financial_position_type": filing_info.financial_position_type,
                "is_going_concern": filing_info.is_going_concern,
                "has_comparative_changes": filing_info.has_comparative_changes,
                "presentation_currency": filing_info.presentation_currency,
                "functional_currency": filing_info.functional_currency,
                "rounding_level": filing_info.rounding_level,
                "entity_operations_description": filing_info.entity_operations_description,
                "principal_place_of_business": filing_info.principal_place_of_business,
                "has_more_than_50_employees": filing_info.has_more_than_50_employees,
                "parent_entity_name": filing_info.parent_entity_name,
                "ultimate_parent_name": filing_info.ultimate_parent_name,
                "taxonomy_version": filing_info.taxonomy_version,
                "xbrl_software": filing_info.xbrl_software,
                "xbrl_preparation_method": filing_info.xbrl_preparation_method
            },
            "directors_statement": {
                "directors_opinion_true_fair_view": xbrl_instance.directors_statement.directors_opinion_true_fair_view,
                "reasonable_grounds_company_debts": xbrl_instance.directors_statement.reasonable_grounds_company_debts
            },
            "audit_report": {
                "audit_opinion": xbrl_instance.audit_report.audit_opinion,
                "auditing_standards": xbrl_instance.audit_report.auditing_standards,
                "material_uncertainty_going_concern": xbrl_instance.audit_report.material_uncertainty_going_concern,
                "proper_accounting_records": xbrl_instance.audit_report.proper_accounting_records
            },
            "statement_of_financial_position": {
                "total_assets": xbrl_instance.statement_of_financial_position.total_assets,
                "total_liabilities": xbrl_instance.statement_of_financial_position.total_liabilities,
                "current_assets": XBRLJSONMapper._get_current_assets_dict(xbrl_instance.statement_of_financial_position.current_assets),
                "noncurrent_assets": XBRLJSONMapper._get_noncurrent_assets_dict(xbrl_instance.statement_of_financial_position.noncurrent_assets),
                "current_liabilities": XBRLJSONMapper._get_current_liabilities_dict(xbrl_instance.statement_of_financial_position.current_liabilities),
                "noncurrent_liabilities": XBRLJSONMapper._get_noncurrent_liabilities_dict(xbrl_instance.statement_of_financial_position.noncurrent_liabilities),
                "equity": XBRLJSONMapper._get_equity_dict(xbrl_instance.statement_of_financial_position.equity)
            },
            "income_statement": XBRLJSONMapper._get_income_statement_dict(xbrl_instance.income_statement),
            "notes": {
                "trade_and_other_receivables": XBRLJSONMapper._get_trade_receivables_dict(xbrl_instance.notes.trade_and_other_receivables),
                "trade_and_other_payables": XBRLJSONMapper._get_trade_payables_dict(xbrl_instance.notes.trade_and_other_payables)
            }
        }
        
        return result
    
    @staticmethod
    def _get_current_assets_dict(current_assets):
        """Helper method to convert CurrentAssets model to dict"""
        return {
            "cash_and_bank_balances": current_assets.cash_and_bank_balances,
            "trade_and_other_receivables": current_assets.trade_and_other_receivables,
            "current_finance_lease_receivables": current_assets.current_finance_lease_receivables,
            "current_derivative_financial_assets": current_assets.current_derivative_financial_assets,
            "current_financial_assets_at_fair_value": current_assets.current_financial_assets_at_fair_value,
            "other_current_financial_assets": current_assets.other_current_financial_assets,
            "development_properties": current_assets.development_properties,
            "inventories": current_assets.inventories,
            "other_current_nonfinancial_assets": current_assets.other_current_nonfinancial_assets,
            "held_for_sale_assets": current_assets.held_for_sale_assets,
            "total_current_assets": current_assets.total_current_assets
        }
    
    @staticmethod
    def _get_noncurrent_assets_dict(noncurrent_assets):
        """Helper method to convert NonCurrentAssets model to dict"""
        return {
            "trade_and_other_receivables": noncurrent_assets.trade_and_other_receivables,
            "noncurrent_finance_lease_receivables": noncurrent_assets.noncurrent_finance_lease_receivables,
            "noncurrent_derivative_financial_assets": noncurrent_assets.noncurrent_derivative_financial_assets,
            "noncurrent_financial_assets_at_fair_value": noncurrent_assets.noncurrent_financial_assets_at_fair_value,
            "other_noncurrent_financial_assets": noncurrent_assets.other_noncurrent_financial_assets,
            "property_plant_equipment": noncurrent_assets.property_plant_equipment,
            "investment_properties": noncurrent_assets.investment_properties,
            "goodwill": noncurrent_assets.goodwill,
            "intangible_assets": noncurrent_assets.intangible_assets,
            "investments_in_entities": noncurrent_assets.investments_in_entities,
            "deferred_tax_assets": noncurrent_assets.deferred_tax_assets,
            "other_noncurrent_nonfinancial_assets": noncurrent_assets.other_noncurrent_nonfinancial_assets,
            "total_noncurrent_assets": noncurrent_assets.total_noncurrent_assets
        }
    
    @staticmethod
    def _get_current_liabilities_dict(current_liabilities):
        """Helper method to convert CurrentLiabilities model to dict"""
        return {
            "trade_and_other_payables": current_liabilities.trade_and_other_payables,
            "current_loans_and_borrowings": current_liabilities.current_loans_and_borrowings,
            "current_financial_liabilities_at_fair_value": current_liabilities.current_financial_liabilities_at_fair_value,
            "current_finance_lease_liabilities": current_liabilities.current_finance_lease_liabilities,
            "other_current_financial_liabilities": current_liabilities.other_current_financial_liabilities,
            "current_income_tax_liabilities": current_liabilities.current_income_tax_liabilities,
            "current_provisions": current_liabilities.current_provisions,
            "other_current_nonfinancial_liabilities": current_liabilities.other_current_nonfinancial_liabilities,
            "liabilities_held_for_sale": current_liabilities.liabilities_held_for_sale,
            "total_current_liabilities": current_liabilities.total_current_liabilities
        }
    
    @staticmethod
    def _get_noncurrent_liabilities_dict(noncurrent_liabilities):
        """Helper method to convert NonCurrentLiabilities model to dict"""
        return {
            "trade_and_other_payables": noncurrent_liabilities.trade_and_other_payables,
            "noncurrent_loans_and_borrowings": noncurrent_liabilities.noncurrent_loans_and_borrowings,
            "noncurrent_financial_liabilities_at_fair_value": noncurrent_liabilities.noncurrent_financial_liabilities_at_fair_value,
            "noncurrent_finance_lease_liabilities": noncurrent_liabilities.noncurrent_finance_lease_liabilities,
            "other_noncurrent_financial_liabilities": noncurrent_liabilities.other_noncurrent_financial_liabilities,
            "deferred_tax_liabilities": noncurrent_liabilities.deferred_tax_liabilities,
            "noncurrent_provisions": noncurrent_liabilities.noncurrent_provisions,
            "other_noncurrent_nonfinancial_liabilities": noncurrent_liabilities.other_noncurrent_nonfinancial_liabilities,
            "total_noncurrent_liabilities": noncurrent_liabilities.total_noncurrent_liabilities
        }
    
    @staticmethod
    def _get_equity_dict(equity):
        """Helper method to convert Equity model to dict"""
        return {
            "share_capital": equity.share_capital,
            "treasury_shares": equity.treasury_shares,
            "accumulated_profits_losses": equity.accumulated_profits_losses,
            "other_reserves": equity.other_reserves,
            "noncontrolling_interests": equity.noncontrolling_interests,
            "total_equity": equity.total_equity
        }
    
    @staticmethod
    def _get_income_statement_dict(income_statement):
        """Helper method to convert IncomeStatement model to dict"""
        return {
            "revenue": income_statement.revenue,
            "other_income": income_statement.other_income,
            "employee_expenses": income_statement.employee_expenses,
            "depreciation_expense": income_statement.depreciation_expense,
            "amortisation_expense": income_statement.amortisation_expense,
            "repairs_and_maintenance_expense": income_statement.repairs_and_maintenance_expense,
            "sales_and_marketing_expense": income_statement.sales_and_marketing_expense,
            "other_expenses_by_nature": income_statement.other_expenses_by_nature,
            "other_gains_losses": income_statement.other_gains_losses,
            "finance_costs": income_statement.finance_costs,
            "share_of_profit_loss_of_associates_and_joint_ventures_accounted_for_using_equity_method": 
                income_statement.share_of_profit_loss_of_associates_and_joint_ventures_accounted_for_using_equity_method,
            "profit_loss_before_taxation": income_statement.profit_loss_before_taxation,
            "tax_expense_benefit_continuing_operations": income_statement.tax_expense_benefit_continuing_operations,
            "profit_loss_from_discontinued_operations": income_statement.profit_loss_from_discontinued_operations,
            "profit_loss": income_statement.profit_loss,
            "profit_loss_attributable_to_owners_of_company": income_statement.profit_loss_attributable_to_owners_of_company,
            "profit_loss_attributable_to_noncontrolling_interests": income_statement.profit_loss_attributable_to_noncontrolling_interests
        }
    
    @staticmethod
    def _get_trade_receivables_dict(trade_receivables):
        """Helper method to convert TradeAndOtherReceivables model to dict"""
        return {
            "receivables_from_third_parties": trade_receivables.receivables_from_third_parties,
            "receivables_from_related_parties": trade_receivables.receivables_from_related_parties,
            "unbilled_receivables": trade_receivables.unbilled_receivables,
            "other_receivables": trade_receivables.other_receivables,
            "total_trade_and_other_receivables": trade_receivables.total_trade_and_other_receivables
        }
        
    