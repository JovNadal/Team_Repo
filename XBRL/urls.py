"""
URL configuration for XBRL project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

# API versioning
api_patterns = [
    path("v1/", include("xbrl_mapping.urls")),
    path("v1/", include("xbrl_validator.urls")),  # Add xbrl_validator URLs
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),  # API with versioning
    path("xbrl/", include("xbrl_mapping.urls")),  # Keep original path for backward compatibility
    path("validate/", include("xbrl_validator.urls")),
    path("tagging/", include("xbrl_tagging.urls")),
]
