from rest_framework import serializers
from .models import (
    FilingInformation, DirectorsStatement, AuditReport, 
    CurrentAssets, NonCurrentAssets, CurrentLiabilities, 
    NonCurrentLiabilities, Equity, StatementOfFinancialPosition,
    IncomeStatement, TradeAndOtherReceivables, Revenue, Notes, PartialXBRL,
    TradeAndOtherPayables
)

class FilingInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FilingInformation
        fields = '__all__'
        read_only_fields = ('id',)

class DirectorsStatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = DirectorsStatement
        fields = '__all__'

class AuditReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditReport
        fields = '__all__'

class CurrentAssetsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrentAssets
        fields = '__all__'

class NonCurrentAssetsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NonCurrentAssets
        fields = '__all__'

class CurrentLiabilitiesSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrentLiabilities
        fields = '__all__'

class NonCurrentLiabilitiesSerializer(serializers.ModelSerializer):
    class Meta:
        model = NonCurrentLiabilities
        fields = '__all__'

class EquitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Equity
        fields = '__all__'

class StatementOfFinancialPositionSerializer(serializers.ModelSerializer):
    current_assets = CurrentAssetsSerializer()
    noncurrent_assets = NonCurrentAssetsSerializer()
    current_liabilities = CurrentLiabilitiesSerializer()
    noncurrent_liabilities = NonCurrentLiabilitiesSerializer()
    equity = EquitySerializer()

    class Meta:
        model = StatementOfFinancialPosition
        fields = '__all__'

class IncomeStatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeStatement
        fields = '__all__'

class TradeAndOtherReceivablesSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeAndOtherReceivables
        fields = '__all__'

class TradeAndOtherPayablesSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeAndOtherPayables
        fields = '__all__'

class RevenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Revenue
        fields = '__all__'

class NotesSerializer(serializers.ModelSerializer):
    trade_and_other_receivables = TradeAndOtherReceivablesSerializer()
    trade_and_other_payables = TradeAndOtherPayablesSerializer()

    class Meta:
        model = Notes
        fields = '__all__'

class PartialXBRLSerializer(serializers.ModelSerializer):
    filing_information = FilingInformationSerializer()
    directors_statement = DirectorsStatementSerializer()
    audit_report = AuditReportSerializer()
    statement_of_financial_position = StatementOfFinancialPositionSerializer()
    income_statement = IncomeStatementSerializer()
    notes = NotesSerializer()

    class Meta:
        model = PartialXBRL
        fields = '__all__'

    def create(self, validated_data):
        # Extract nested data
        filing_info_data = validated_data.pop('filing_information')
        directors_statement_data = validated_data.pop('directors_statement')
        audit_report_data = validated_data.pop('audit_report')
        
        # Extract statement of financial position data and its nested components
        sof_position_data = validated_data.pop('statement_of_financial_position')
        current_assets_data = sof_position_data.pop('current_assets')
        noncurrent_assets_data = sof_position_data.pop('noncurrent_assets')
        current_liabilities_data = sof_position_data.pop('current_liabilities')
        noncurrent_liabilities_data = sof_position_data.pop('noncurrent_liabilities')
        equity_data = sof_position_data.pop('equity')
        income_statement_data = validated_data.pop('income_statement')
        
        # Extract notes data and its nested components
        notes_data = validated_data.pop('notes')
        trade_receivables_data = notes_data.pop('trade_and_other_receivables')
        trade_payables_data = notes_data.pop('trade_and_other_payables')

        # Create filing information first
        filing_info = FilingInformation.objects.create(**filing_info_data)
        
        # Create directors statement and audit report
        directors_statement = DirectorsStatement.objects.create(filing=filing_info, **directors_statement_data)
        audit_report = AuditReport.objects.create(filing=filing_info, **audit_report_data)
        
        # Create financial position components
        current_assets = CurrentAssets.objects.create(filing=filing_info, **current_assets_data)
        noncurrent_assets = NonCurrentAssets.objects.create(filing=filing_info, **noncurrent_assets_data)
        current_liabilities = CurrentLiabilities.objects.create(filing=filing_info, **current_liabilities_data)
        noncurrent_liabilities = NonCurrentLiabilities.objects.create(filing=filing_info, **noncurrent_liabilities_data)
        equity = Equity.objects.create(filing=filing_info, **equity_data)
        
        # Create statement of financial position
        sof_position = StatementOfFinancialPosition.objects.create(
            filing=filing_info,
            current_assets=current_assets,
            noncurrent_assets=noncurrent_assets,
            current_liabilities=current_liabilities,
            noncurrent_liabilities=noncurrent_liabilities,
            equity=equity,
            **sof_position_data
        )
        
        # Create income statement
        income_statement = IncomeStatement.objects.create(filing=filing_info, **income_statement_data)
        
        # Create notes components
        trade_receivables = TradeAndOtherReceivables.objects.create(filing=filing_info, **trade_receivables_data)
        trade_payables = TradeAndOtherPayables.objects.create(filing=filing_info, **trade_payables_data)
        
        # Create notes
        notes = Notes.objects.create(
            filing=filing_info,
            trade_and_other_receivables=trade_receivables,
            trade_and_other_payables=trade_payables,
            **notes_data
        )
        
        # Finally create the partial XBRL object
        xbrl = PartialXBRL.objects.create(
            filing_information=filing_info,
            directors_statement=directors_statement,
            audit_report=audit_report,
            statement_of_financial_position=sof_position,
            income_statement=income_statement,
            notes=notes,
            **validated_data
        )
        
        return xbrl

    def update(self, instance, validated_data):
        # Handle nested updates
        if 'filing_information' in validated_data:
            filing_info_data = validated_data.pop('filing_information')
            filing_info = instance.filing_information
            for attr, value in filing_info_data.items():
                setattr(filing_info, attr, value)
            filing_info.save()
        
        # Handle directors statement update
        if 'directors_statement' in validated_data:
            directors_data = validated_data.pop('directors_statement')
            directors = instance.directors_statement
            for attr, value in directors_data.items():
                setattr(directors, attr, value)
            directors.save()
        
        # Handle audit report update
        if 'audit_report' in validated_data:
            audit_data = validated_data.pop('audit_report')
            audit = instance.audit_report
            for attr, value in audit_data.items():
                setattr(audit, attr, value)
            audit.save()
        
        # Handle statement of financial position and its nested components
        if 'statement_of_financial_position' in validated_data:
            sof_data = validated_data.pop('statement_of_financial_position')
            sof = instance.statement_of_financial_position
            
            # Update current assets
            if 'current_assets' in sof_data:
                current_assets_data = sof_data.pop('current_assets')
                current_assets = sof.current_assets
                for attr, value in current_assets_data.items():
                    setattr(current_assets, attr, value)
                current_assets.save()
            
            # Update noncurrent assets
            if 'noncurrent_assets' in sof_data:
                noncurrent_assets_data = sof_data.pop('noncurrent_assets')
                noncurrent_assets = sof.noncurrent_assets
                for attr, value in noncurrent_assets_data.items():
                    setattr(noncurrent_assets, attr, value)
                noncurrent_assets.save()
            
            # Update current liabilities
            if 'current_liabilities' in sof_data:
                current_liabilities_data = sof_data.pop('current_liabilities')
                current_liabilities = sof.current_liabilities
                for attr, value in current_liabilities_data.items():
                    setattr(current_liabilities, attr, value)
                current_liabilities.save()
            
            # Update noncurrent liabilities
            if 'noncurrent_liabilities' in sof_data:
                noncurrent_liabilities_data = sof_data.pop('noncurrent_liabilities')
                noncurrent_liabilities = sof.noncurrent_liabilities
                for attr, value in noncurrent_liabilities_data.items():
                    setattr(noncurrent_liabilities, attr, value)
                noncurrent_liabilities.save()
            
            # Update equity
            if 'equity' in sof_data:
                equity_data = sof_data.pop('equity')
                equity = sof.equity
                for attr, value in equity_data.items():
                    setattr(equity, attr, value)
                equity.save()
            
            # Update remaining statement of financial position fields
            for attr, value in sof_data.items():
                setattr(sof, attr, value)
            sof.save()
        
        # Handle income statement update
        if 'income_statement' in validated_data:
            income_data = validated_data.pop('income_statement')
            income = instance.income_statement
            for attr, value in income_data.items():
                setattr(income, attr, value)
            income.save()
        
        # Handle notes and its nested components
        if 'notes' in validated_data:
            notes_data = validated_data.pop('notes')
            notes = instance.notes
            
            # Update trade and other receivables
            if 'trade_and_other_receivables' in notes_data:
                receivables_data = notes_data.pop('trade_and_other_receivables')
                receivables = notes.trade_and_other_receivables
                for attr, value in receivables_data.items():
                    setattr(receivables, attr, value)
                receivables.save()
            
            # Update trade and other payables
            if 'trade_and_other_payables' in notes_data:
                payables_data = notes_data.pop('trade_and_other_payables')
                payables = notes.trade_and_other_payables
                for attr, value in payables_data.items():
                    setattr(payables, attr, value)
                payables.save()
            
            # Update remaining notes fields
            for attr, value in notes_data.items():
                setattr(notes, attr, value)
            notes.save()
        
        # Update remaining PartialXBRL fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance