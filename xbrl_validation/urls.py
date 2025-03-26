from django.urls import path
from . import views

app_name = 'validation'

urlpatterns = [
    path('process/', views.validate_mapped_data, name='validate_mapped_data'),
]