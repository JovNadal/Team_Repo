#!/usr/bin/env python
"""
Test script to demonstrate the error_response utility.
"""
import os
import sys
import django
import json
from pprint import pprint

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'XBRL.settings')
django.setup()

from xbrl_validator.utils import error_response

def demonstrate_error_response():
    """
    Demonstrate different ways to use the error_response utility
    """
    print("\n=== Example 1: Simple error message ===")
    response = error_response("Invalid data format")
    pprint(response.data)
    
    print("\n=== Example 2: Pre-formatted list of errors ===")
    errors = [
        {"section": "filing_information", "message": "Missing required field: company_name"},
        {"section": "financial_position", "message": "Total assets do not match current + non-current assets"}
    ]
    response = error_response("XBRL validation failed", errors=errors)
    pprint(response.data)
    
    print("\n=== Example 3: Dictionary of errors by section ===")
    errors_by_section = {
        "filing_information": [
            "Missing required field: company_name",
            "Invalid UEN format"
        ],
        "financial_position": [
            "Total assets do not match current + non-current assets"
        ]
    }
    response = error_response("XBRL validation failed", errors=errors_by_section)
    pprint(response.data)
    
    print("\n=== Example 4: Server error with custom status code ===")
    response = error_response(
        "Database connection failed",
        status_code=500
    )
    pprint(response.data)
    
if __name__ == "__main__":
    demonstrate_error_response() 