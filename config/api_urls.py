"""
URL Configuration for API.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from dashboards.views import DashboardInstanceViewSet, DataSourceViewSet

# Router para endpoints do DRF
router = DefaultRouter()
router.register(r'dashboards', DashboardInstanceViewSet, basename='dashboard')
router.register(r'datasources', DataSourceViewSet, basename='datasource')

urlpatterns = [
    # Auth endpoints
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # API endpoints
    path('', include(router.urls)),
]
