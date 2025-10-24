from django.shortcuts import render
from django.http import JsonResponse
from .models.boiler_model import BoilerModel
import json

def dashboard(request):
    """Главная страница с параметрами"""
    return render(request, 'boiler_monitor/dashboard.html')

def charts(request):
    """Страница с графиками"""
    return render(request, 'boiler_monitor/charts.html')

def api_current_data(request):
    """API для получения текущих данных"""
    boiler = BoilerModel()
    data = boiler.get_current_data()
    return JsonResponse(data)

def api_chart_data(request):
    """API для получения данных графиков"""
    boiler = BoilerModel()
    data = boiler.get_chart_data()
    return JsonResponse(data)

def api_update_setpoint(request):
    """API для обновления уставок"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            boiler = BoilerModel()
            
            if 'pressure_setpoint' in data:
                boiler.p_z = float(data['pressure_setpoint'])
            if 'water_level_setpoint' in data:
                boiler.M_v_z = float(data['water_level_setpoint'])
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'})