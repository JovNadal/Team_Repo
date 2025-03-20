from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import ValidationResult, ValidationError
from .utils import success_response, error_response
from .validators import ACRAXBRLValidator

class XBRLValidatorTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.valid_data = {
            "filing_information": {
                "company_name": "Test Company",
                "unique_entity_number": "201912345D",
                "current_period_start": "2023-01-01",
                "current_period_end": "2023-12-31",
                "taxonomy_version": "2022.2",
                "xbrl_filing_type": "Full",
                "financial_statement_type": "Company"
            },
            "statement_of_financial_position": {
                "total_assets": 1000,
                "current_assets": {"total_current_assets": 500},
                "noncurrent_assets": {"total_noncurrent_assets": 500},
                "total_liabilities": 500,
                "current_liabilities": {"total_current_liabilities": 300},
                "noncurrent_liabilities": {"total_noncurrent_liabilities": 200},
                "equity": {"total_equity": 500}
            },
            "income_statement": {
                "revenue": 1000,
                "total_expenses": 500,
                "profit_loss": 500
            }
        }
        self.invalid_data = {
            "filing_information": {
                "company_name": "",
                "unique_entity_number": "INVALID_UEN",
                "current_period_start": "2023-01-01",
                "current_period_end": "2023-12-31",
                "taxonomy_version": "2022.2",
                "xbrl_filing_type": "Full",
                "financial_statement_type": "Company"
            }
        }

    def test_success_response(self):
        response = success_response("Test success", {"key": "value"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['message'], "Test success")
        self.assertIn('data', response.data)

    def test_error_response(self):
        response = error_response("Test error", status_code=status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['message'], "Test error")

    def test_acra_xbrl_validator_valid_data(self):
        validator = ACRAXBRLValidator(self.valid_data)
        is_valid, errors = validator.validate()
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_acra_xbrl_validator_invalid_data(self):
        validator = ACRAXBRLValidator(self.invalid_data)
        is_valid, errors = validator.validate()
        self.assertFalse(is_valid)
        self.assertIn('filing_information', errors)
