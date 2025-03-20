from django.urls import path
from . import views

urlpatterns = [
    path('tag/', views.tag_financial_data, name='tag_financial_data'),
]