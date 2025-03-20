from django.urls import path
from . import views

urlpatterns = [
    path('validate/', views.validate_mapped_data, name='validate_mapped_data'),
]