from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('charts/', views.charts, name='charts'),
    path('api/current-data/', views.api_current_data, name='api_current_data'),
    path('api/chart-data/', views.api_chart_data, name='api_chart_data'),
    path('api/update-setpoint/', views.api_update_setpoint, name='api_update_setpoint'),
]