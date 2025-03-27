from django.urls import path
from . import views

urlpatterns = [
    # Main XBRL endpoints
    path('partial-xbrl/', views.PartialXBRLListCreateView.as_view(), name='partial-xbrl-list-create'),
    path('partial-xbrl/<uuid:pk>/', views.PartialXBRLDetailView.as_view(), name='partial-xbrl-detail'),

    path('simple/', views.SimpleXBRLView.as_view(), name='xbrl-simple'),
    # path('simple/<uuid:pk>/', views.SimpleXBRLDetailView.as_view(), name='xbrl-simple-detail'),
    # path('full/', views.FullXBRLView.as_view(), name='xbrl-full'),
    # path('full/<uuid:pk>/', views.FullXBRLDetailView.as_view(), name='xbrl-full-detail'),
    path('search/', views.XBRLSearchView.as_view(), name='xbrl-search'),

    # Mapping endpoints
    path('map/', views.map_financial_data, name='map_financial_data'),
    path('update/<uuid:id>/', views.update_mapped_data, name='update-mapped-data'),

    path('status/<str:task_id>/', views.check_task_status, name='check-task-status'),
]
