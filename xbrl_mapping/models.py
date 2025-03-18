from django.db import models
import uuid

class XBRLFiling(models.TextChoices):
    FULL = "Full", "Full"
    PARTIAL = "Partial", "Partial"

class FinancialStatementType(models.TextChoices):
    COMPANY = "Company", "Company"
    CONSOLIDATED = "Consolidated", "Consolidated"

class AccountingStandard(models.TextChoices):
    SFRS = "SFRS", "SFRS"
    SFRS_SE = "SFRS for SE", "SFRS for SE"
    IFRS = "IFRS", "IFRS"
    OTHER = "Other", "Other"

class StatementOfFinancialPositionType(models.TextChoices):
    CLASSIFIED = "Classified", "Classified"
    LIQUIDITY = "Liquidity-based", "Liquidity-based"

class RoundingLevel(models.TextChoices):
    THOUSANDS = "Thousands", "Thousands"
    MILLIONS = "Millions", "Millions"
    UNITS = "Units", "Units"

class XBRLPreparationMethod(models.TextChoices):
    AUTOMATED = "Automated", "Automated"
    MANUAL = "Manual", "Manual"
    HYBRID = "Hybrid", "Hybrid"

class AuditOpinion(models.TextChoices):
    UNQUALIFIED = "Unqualified", "Unqualified"
    QUALIFIED = "Qualified", "Qualified"
    ADVERSE = "Adverse", "Adverse"
    DISCLAIMER = "Disclaimer", "Disclaimer"

class FilingInformation(models.Model):
    """Basic entity and filing information"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_name = models.CharField(max_length=255)
    unique_entity_number = models.CharField(
        max_length=10,
        unique=True
    )
    current_period_start = models.CharField(max_length=10)
    current_period_end = models.CharField(max_length=10)
    prior_period_start = models.CharField(max_length=10, null=True, blank=True)
    xbrl_filing_type = models.CharField(max_length=10, choices=XBRLFiling.choices)
    financial_statement_type = models.CharField(max_length=15, choices=FinancialStatementType.choices)
    accounting_standard = models.CharField(max_length=15, choices=AccountingStandard.choices, db_column='accounting_standard')
    authorisation_date = models.CharField(max_length=10)
    financial_position_type = models.CharField(max_length=15, choices=StatementOfFinancialPositionType.choices)
    is_going_concern = models.BooleanField(db_column='is_going_concern')
    has_comparative_changes = models.BooleanField()
    presentation_currency = models.CharField(max_length=255)
    functional_currency = models.CharField(max_length=255)
    rounding_level = models.CharField(max_length=15, choices=RoundingLevel.choices)
    entity_operations_description = models.TextField(db_column='entity_operations_description')
    principal_place_of_business = models.CharField(max_length=255)
    has_more_than_50_employees = models.BooleanField()
    parent_entity_name = models.CharField(max_length=255, null=True, blank=True)
    ultimate_parent_name = models.CharField(max_length=255, null=True, blank=True)
    taxonomy_version = models.CharField(max_length=10, default="2022.2")
    xbrl_software = models.CharField(max_length=255)
    xbrl_preparation_method = models.CharField(max_length=15, choices=XBRLPreparationMethod.choices)
    
class DirectorsStatement(models.Model):
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    directors_opinion_true_fair_view = models.BooleanField(db_column='directors_opinion_true_fair_view')
    reasonable_grounds_company_debts = models.BooleanField(db_column='reasonable_grounds_company_debts')

class AuditReport(models.Model):
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    audit_opinion = models.CharField(max_length=15, choices=AuditOpinion.choices)
    auditing_standards = models.CharField(max_length=255, null=True, blank=True)
    material_uncertainty_going_concern = models.BooleanField(null=True, blank=True)
    proper_accounting_records = models.BooleanField(null=True, blank=True)

class CurrentAssets(models.Model):
    """Current assets section"""
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    cash_and_bank_balances = models.FloatField(null=True, blank=True)
    trade_and_other_receivables = models.FloatField(null=True, blank=True)
    current_finance_lease_receivables = models.FloatField(null=True, blank=True)
    current_derivative_financial_assets = models.FloatField(null=True, blank=True)
    current_financial_assets_at_fair_value = models.FloatField(
        null=True, blank=True, db_column='current_financial_assets_at_fair_value'
    )
    other_current_financial_assets = models.FloatField(null=True, blank=True)
    development_properties = models.FloatField(null=True, blank=True)
    inventories = models.FloatField(null=True, blank=True)
    other_current_nonfinancial_assets = models.FloatField(null=True, blank=True)
    held_for_sale_assets = models.FloatField(
        null=True, blank=True, db_column='held_for_sale_assets'
    )
    total_current_assets = models.FloatField()

class NonCurrentAssets(models.Model):
    """Non-current assets section"""
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    trade_and_other_receivables = models.FloatField(null=True, blank=True)
    noncurrent_finance_lease_receivables = models.FloatField(null=True, blank=True)
    noncurrent_derivative_financial_assets = models.FloatField(null=True, blank=True)
    noncurrent_financial_assets_at_fair_value = models.FloatField(
        null=True, blank=True, db_column='noncurrent_financial_assets_at_fair_value'
    )
    other_noncurrent_financial_assets = models.FloatField(null=True, blank=True)
    property_plant_equipment = models.FloatField(null=True, blank=True)
    investment_properties = models.FloatField(null=True, blank=True)
    goodwill = models.FloatField(null=True, blank=True)
    intangible_assets = models.FloatField(null=True, blank=True)
    investments_in_entities = models.FloatField(null=True, blank=True)
    deferred_tax_assets = models.FloatField(null=True, blank=True)
    other_noncurrent_nonfinancial_assets = models.FloatField(null=True, blank=True)
    total_noncurrent_assets = models.FloatField()

class CurrentLiabilities(models.Model):
    """Current liabilities section"""
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    trade_and_other_payables = models.FloatField(null=True, blank=True)
    current_loans_and_borrowings = models.FloatField(null=True, blank=True)
    current_financial_liabilities_at_fair_value = models.FloatField(
        null=True, blank=True, db_column='current_financial_liabilities_at_fair_value'
    )
    current_finance_lease_liabilities = models.FloatField(null=True, blank=True)
    other_current_financial_liabilities = models.FloatField(null=True, blank=True)
    current_income_tax_liabilities = models.FloatField(null=True, blank=True)
    current_provisions = models.FloatField(null=True, blank=True)
    other_current_nonfinancial_liabilities = models.FloatField(null=True, blank=True)
    liabilities_held_for_sale = models.FloatField(null=True, blank=True)
    total_current_liabilities = models.FloatField()

class NonCurrentLiabilities(models.Model):
    """Non-current liabilities section"""
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    trade_and_other_payables = models.FloatField(null=True, blank=True)
    noncurrent_loans_and_borrowings = models.FloatField(null=True, blank=True)
    noncurrent_financial_liabilities_at_fair_value = models.FloatField(
        null=True, blank=True, db_column='noncurrent_financial_liabilities_at_fair_value'
    )
    noncurrent_finance_lease_liabilities = models.FloatField(null=True, blank=True)
    other_noncurrent_financial_liabilities = models.FloatField(null=True, blank=True)
    deferred_tax_liabilities = models.FloatField(null=True, blank=True)
    noncurrent_provisions = models.FloatField(null=True, blank=True)
    other_noncurrent_nonfinancial_liabilities = models.FloatField(null=True, blank=True)
    total_noncurrent_liabilities = models.FloatField()

class Equity(models.Model):
    """Equity section"""
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    share_capital = models.FloatField()
    treasury_shares = models.FloatField(null=True, blank=True)
    accumulated_profits_losses = models.FloatField()
    other_reserves = models.FloatField(null=True, blank=True)
    noncontrolling_interests = models.FloatField(null=True, blank=True)
    total_equity = models.FloatField()

class StatementOfFinancialPosition(models.Model):
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    current_assets = models.OneToOneField(CurrentAssets, on_delete=models.CASCADE)
    noncurrent_assets = models.OneToOneField(NonCurrentAssets, on_delete=models.CASCADE)
    total_assets = models.FloatField()
    current_liabilities = models.OneToOneField(CurrentLiabilities, on_delete=models.CASCADE)
    noncurrent_liabilities = models.OneToOneField(NonCurrentLiabilities, on_delete=models.CASCADE)
    total_liabilities = models.FloatField()
    equity = models.OneToOneField(Equity, on_delete=models.CASCADE)

class IncomeStatement(models.Model):
    """Income statement information"""
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    revenue = models.FloatField()
    other_income = models.FloatField(null=True, blank=True)
    employee_expenses = models.FloatField(null=True, blank=True)
    depreciation_expense = models.FloatField(null=True, blank=True)
    amortisation_expense = models.FloatField(null=True, blank=True)
    repairs_and_maintenance_expense = models.FloatField(null=True, blank=True)
    sales_and_marketing_expense = models.FloatField(null=True, blank=True)
    other_expenses_by_nature = models.FloatField(null=True, blank=True)
    other_gains_losses = models.FloatField(null=True, blank=True)
    finance_costs = models.FloatField(null=True, blank=True)
    share_of_profit_loss_of_associates_and_joint_ventures_accounted_for_using_equity_method = models.FloatField(
        null=True, blank=True, db_column='profit_loss_associates_equity_method'
    )
    profit_loss_before_taxation = models.FloatField(null=True, blank=True)
    tax_expense_benefit_continuing_operations = models.FloatField(null=True, blank=True)
    profit_loss_from_discontinued_operations = models.FloatField(null=True, blank=True)
    profit_loss = models.FloatField()
    profit_loss_attributable_to_owners_of_company = models.FloatField(null=True, blank=True)
    profit_loss_attributable_to_noncontrolling_interests = models.FloatField(null=True, blank=True)

class TradeAndOtherReceivables(models.Model):
    """Trade and other receivables detail"""
    filing = models.ForeignKey(FilingInformation, on_delete=models.CASCADE, related_name='receivables')
    receivables_from_third_parties = models.FloatField(null=True, blank=True, help_text="Receivables from third parties. Common terms: third party receivables, external receivables")
    receivables_from_related_parties = models.FloatField(null=True, blank=True, help_text="Receivables from related parties. Common terms: related party receivables, intercompany receivables")
    unbilled_receivables = models.FloatField(null=True, blank=True, help_text="Unbilled receivables. Common terms: contract assets, accrued income, work completed not billed")
    other_receivables = models.FloatField(null=True, blank=True, help_text="Other receivables. Common terms: sundry receivables, miscellaneous receivables, deposits")
    total_trade_and_other_receivables = models.FloatField(help_text="Total trade and other receivables. Common terms: accounts receivable, debtors, total receivables")

class TradeAndOtherPayables(models.Model):
    """Trade and other payables detail"""
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE, related_name='payables')
    payables_to_third_parties = models.FloatField(null=True, blank=True, help_text="Payables to third parties")
    payables_to_related_parties = models.FloatField(null=True, blank=True, help_text="Payables to related parties")
    accrued_liabilities = models.FloatField(null=True, blank=True, help_text="Accrued liabilities")
    other_payables = models.FloatField(null=True, blank=True, help_text="Other payables")
    total_trade_and_other_payables = models.FloatField(help_text="Total trade and other payables")

class Revenue(models.Model):
    """Revenue details"""
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    revenue_from_property_point_in_time = models.FloatField(null=True, blank=True)
    revenue_from_goods_point_in_time = models.FloatField(null=True, blank=True)
    revenue_from_services_point_in_time = models.FloatField(null=True, blank=True)
    revenue_from_property_over_time = models.FloatField(null=True, blank=True)
    revenue_from_construction_over_time = models.FloatField(null=True, blank=True)
    revenue_from_services_over_time = models.FloatField(null=True, blank=True)
    other_revenue = models.FloatField(null=True, blank=True)
    total_revenue = models.FloatField()

class Notes(models.Model):
    """Notes to financial statements"""
    filing = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    trade_and_other_receivables = models.OneToOneField(
        TradeAndOtherReceivables, 
        on_delete=models.CASCADE, 
        related_name='notes_receivables'
    )
    trade_and_other_payables = models.OneToOneField(
        TradeAndOtherPayables, 
        on_delete=models.CASCADE, 
        related_name='notes_payables'
    )

class PartialXBRL(models.Model):
    """Singapore XBRL schema"""
    filing_information = models.OneToOneField(FilingInformation, on_delete=models.CASCADE)
    directors_statement = models.OneToOneField(DirectorsStatement, on_delete=models.CASCADE)
    audit_report = models.OneToOneField(AuditReport, on_delete=models.CASCADE)
    statement_of_financial_position = models.OneToOneField(StatementOfFinancialPosition, on_delete=models.CASCADE)
    income_statement = models.OneToOneField(IncomeStatement, on_delete=models.CASCADE)
    notes = models.OneToOneField(Notes, on_delete=models.CASCADE)
