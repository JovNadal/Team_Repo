from django.urls import path
from . import views

urlpatterns = [
    path('process/', views.validate_mapped_data, name='validate_mapped_data'),
]
