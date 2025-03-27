"""
Update processor for XBRL data.

This module handles updating existing XBRL financial data in the database.
"""
import logfire
import json
from typing import Dict, Any, List
from django.db import transaction

from .storage import map_pydantic_to_django_fields


def process_update_data(xbrl_instance, mapped_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process update for existing XBRL data
    
    Args:
        xbrl_instance: The PartialXBRL instance to update
        mapped_data: The mapped data with updates
        
    Returns:
        Dict with update status and any errors
    """
    logfire.debug("Processing update data", data_size=len(json.dumps(mapped_data)))
    
    # If data is still in PascalCase, convert it to snake_case
    if any(key for key in mapped_data.keys() if key[0].isupper()):
        mapped_data = map_pydantic_to_django_fields(mapped_data)
    
    if 'filing_information' not in mapped_data:
        mapped_data['filing_information'] = {}
    
    # Preserve the UEN to ensure we're updating the same record
    uen = xbrl_instance.filing_information.unique_entity_number
    mapped_data['filing_information']['unique_entity_number'] = uen
    
    # Validate that no ID fields are being modified - this is a security measure
    forbidden_fields = _check_forbidden_field_modifications(xbrl_instance, mapped_data)
    
    if forbidden_fields:
        return {
            'success': False,
            'message': "Modification of ID or relationship fields is not allowed",
            'error': f"The following fields cannot be modified: {', '.join(forbidden_fields)}"
        }
    
    # Handle the transaction to avoid constraint violations
    with transaction.atomic():
        try:
            # Store old ID for reference
            old_id = xbrl_instance.id
            
            # Get filing information ID before updating
            filing_info_id = xbrl_instance.filing_information.id
            
            # Update the entities
            _update_filing_information(xbrl_instance, mapped_data)
            _update_directors_statement(xbrl_instance, mapped_data)
            _update_audit_report(xbrl_instance, mapped_data)
            _update_financial_position(xbrl_instance, mapped_data)
            _update_income_statement(xbrl_instance, mapped_data)
            _update_notes(xbrl_instance, mapped_data)
            
            logfire.info(f"Successfully updated financial data in database. ID: {xbrl_instance.id}")
            
            return {
                'success': True,
                'message': f"Financial data for UEN {uen} updated successfully",
                'filing_id': str(xbrl_instance.id)
            }
            
        except Exception as e:
            logfire.exception("Error during database update transaction", error=str(e))
            return {
                'success': False,
                'message': "Database transaction failed during update",
                'error': str(e)
            }


def _check_forbidden_field_modifications(xbrl_instance, mapped_data: Dict[str, Any]) -> List[str]:
    """
    Check for attempts to modify forbidden fields (ID fields and relationship fields)
    
    Args:
        xbrl_instance: The XBRL instance to check against
        mapped_data: The mapped data with updates
        
    Returns:
        List of forbidden field modifications found
    """
    forbidden_fields = []
    
    # Check filing_information
    if 'filing_information' in mapped_data:
        filing_info = xbrl_instance.filing_information
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
            section_obj = getattr(xbrl_instance, section, None)
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
                _check_financial_position_components(section_obj, mapped_data[section], section, forbidden_fields)
            
            # Check nested components in notes
            if section == 'notes':
                _check_notes_components(section_obj, mapped_data[section], section, forbidden_fields)
    
    return forbidden_fields


def _check_financial_position_components(section_obj, section_data, section_name, forbidden_fields):
    """Check for forbidden field modifications in financial position components"""
    for component in ['current_assets', 'noncurrent_assets', 'current_liabilities', 
                     'noncurrent_liabilities', 'equity']:
        if component in section_data:
            component_obj = getattr(section_obj, component, None)
            if not component_obj:
                continue
            
            for field in section_data[component]:
                if field == 'id' or field == 'filing' or field.endswith('_id'):
                    # Only add to forbidden fields if the value is actually changing
                    current_value = getattr(component_obj, field, None)
                    new_value = section_data[component][field]
                    if str(current_value) != str(new_value):
                        forbidden_fields.append(f"{section_name}.{component}.{field}")


def _check_notes_components(section_obj, section_data, section_name, forbidden_fields):
    """Check for forbidden field modifications in notes components"""
    for component in ['trade_and_other_receivables', 'trade_and_other_payables', 'revenue']:
        if component in section_data:
            component_obj = getattr(section_obj, component, None)
            if not component_obj:
                continue
                
            for field in section_data[component]:
                if field == 'id' or field == 'filing' or field.endswith('_id'):
                    # Only add to forbidden fields if the value is actually changing
                    current_value = getattr(component_obj, field, None)
                    new_value = section_data[component][field]
                    if str(current_value) != str(new_value):
                        forbidden_fields.append(f"{section_name}.{component}.{field}")


def _update_filing_information(xbrl_instance, mapped_data):
    """Update filing information"""
    if 'filing_information' in mapped_data:
        filing_info_data = mapped_data.get('filing_information', {})
        filing_info = xbrl_instance.filing_information
        
        # Update filing info fields - FORBID id and _id fields
        for field, value in filing_info_data.items():
            if (hasattr(filing_info, field) and 
                field != 'id' and 
                not field.endswith('_id')):
                setattr(filing_info, field, value)
        filing_info.save()


def _update_directors_statement(xbrl_instance, mapped_data):
    """Update directors statement"""
    if 'directors_statement' in mapped_data and xbrl_instance.directors_statement:
        dirs_stmt_data = mapped_data.get('directors_statement', {})
        dirs_stmt = xbrl_instance.directors_statement
        for field, value in dirs_stmt_data.items():
            # FORBID id, filing and _id fields
            if (hasattr(dirs_stmt, field) and 
                field != 'filing' and 
                field != 'id' and 
                not field.endswith('_id')):
                setattr(dirs_stmt, field, value)
        dirs_stmt.save()


def _update_audit_report(xbrl_instance, mapped_data):
    """Update audit report"""
    if 'audit_report' in mapped_data and xbrl_instance.audit_report:
        audit_data = mapped_data.get('audit_report', {})
        audit = xbrl_instance.audit_report
        for field, value in audit_data.items():
            # FORBID id, filing and _id fields
            if (hasattr(audit, field) and 
                field != 'filing' and 
                field != 'id' and 
                not field.endswith('_id')):
                setattr(audit, field, value)
        audit.save()


def _update_financial_position(xbrl_instance, mapped_data):
    """Update statement of financial position"""
    if 'statement_of_financial_position' in mapped_data and xbrl_instance.statement_of_financial_position:
        position_data = mapped_data.get('statement_of_financial_position', {})
        position = xbrl_instance.statement_of_financial_position
        
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


def _update_income_statement(xbrl_instance, mapped_data):
    """Update income statement"""
    if 'income_statement' in mapped_data and xbrl_instance.income_statement:
        income_data = mapped_data.get('income_statement', {})
        income = xbrl_instance.income_statement
        for field, value in income_data.items():
            # FORBID id, filing and _id fields
            if (hasattr(income, field) and 
                field != 'filing' and 
                field != 'id' and 
                not field.endswith('_id')):
                setattr(income, field, value)
        income.save()


def _update_notes(xbrl_instance, mapped_data):
    """Update notes"""
    if 'notes' in mapped_data and xbrl_instance.notes:
        notes_data = mapped_data.get('notes', {})
        notes = xbrl_instance.notes
        
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