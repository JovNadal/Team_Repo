from django.urls import path
from . import views

urlpatterns = [
    # Main XBRL endpoints
    path('partial-xbrl/', views.PartialXBRLListCreateView.as_view(), name='partial-xbrl-list-create'),
    path('partial-xbrl/<uuid:pk>/', views.PartialXBRLDetailView.as_view(), name='partial-xbrl-detail'),
    
    # Component endpoints
    path('filing-information/', views.FilingInformationListView.as_view(), name='filing-information-list'),
    path('filing-information/<uuid:pk>/', views.FilingInformationDetailView.as_view(), name='filing-information-detail'),
    
    path('financial-position/', views.StatementOfFinancialPositionListView.as_view(), name='financial-position-list'),
    path('financial-position/<uuid:filing_id>/', views.StatementOfFinancialPositionDetailView.as_view(), name='financial-position-detail'),
    
    path('income-statement/', views.IncomeStatementListView.as_view(), name='income-statement-list'),
    path('income-statement/<uuid:filing_id>/', views.IncomeStatementDetailView.as_view(), name='income-statement-detail'),
    
    path('notes/', views.NotesListView.as_view(), name='notes-list'),
    path('notes/<uuid:filing_id>/', views.NotesDetailView.as_view(), name='notes-detail'),
    
    # Utility endpoints
    path('search/', views.XBRLSearchView.as_view(), name='xbrl-search'),
    path('template/', views.get_xbrl_template, name='xbrl-template'),
    path('validate/', views.validate_xbrl_json, name='xbrl-validate'),
    path('bulk/', views.bulk_operations, name='xbrl-bulk-operations'),
    path('by-uen/<str:uen>/', views.get_xbrl_by_uen, name='xbrl-by-uen'),
]
