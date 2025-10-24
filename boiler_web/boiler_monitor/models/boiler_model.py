import numpy as np
from scipy.interpolate import interp1d
import threading
import time
import json

from datetime import datetime  
class BoilerModel:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BoilerModel, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        # Параметры модели (как в MATLAB)
        self.dt = 0.05
        self.running = True
        
        # Данные модели (как в MATLAB)
        self.t = [0.0]
        self.t_v = [173.9754]  # температура воды
        self.t_k = [278.1349]  # температура топки
        self.p = [8.9951e5]    # давление
        self.M_v = [2500.0]    # масса воды
        self.M_p = [32.6929]   # масса пара
        self.G_p = [0.0]       # расход пара
        self.pi = [8.9951e5]   # измеренное давление
        
        # Теплофизические характеристики (как в MATLAB)
        self.c_v = 1 * 4.19e3
        self.c_k = 1500
        self.M = 18e-3
        self.R = 8.31
        self.ro_p = 8.4
        self.ro_k = 1
        self.ro_v = 1000
        self.r_t = 3.6e7
        self.Lamda = 1945e3
        
        # Параметры котла (как в MATLAB)
        self.V_0 = 10
        self.K = 1500
        self.F = 10
        self.G_v_n = 0.6032
        self.t_v_vx = 20
        self.t_t_vx = 20
        self.p_t = 2 * 9.81e4
        self.p_pot = 5 * 9.81e4
        self.p_k = 1 * 9.81e4
        
        # Клапаны (как в MATLAB)
        self.mu1 = 0.0000008
        self.mu2_n = 0.0000002
        
        # Характеристики пара (как в MATLAB)
        self.xx = np.array([0.98, 0.99, 1, 1.01, 1.013, 1.02, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 40]) * 1e5
        self.yy = np.array([99.23, 99.46, 99.7, 99.93, 100, 100.27, 120, 133, 143, 151, 158, 164, 169, 174, 179, 212, 250])
        self.p_interp = interp1d(self.yy, self.xx, kind='linear', bounds_error=False, fill_value='extrapolate')
        
        # ПИ-регуляторы (как в MATLAB)
        self.sum = 0
        self.sum2 = 0
        self.Kp2 = 0.000000000002
        self.Ti2 = 100
        self.Kp = 20
        self.Ti = 20
        self.p_z = 9.9951e5
        self.M_v_z = 2500
        
        # Датчики и ИМ (как в MATLAB)
        self.Td = 10
        self.Tim = 20
        self.mu2_old = 0.0000002  # начальное значение как в MATLAB
        
        # Запуск потока расчета
        self.thread = threading.Thread(target=self._run_simulation)
        self.thread.daemon = True
        self.thread.start()
    
    def _run_simulation(self):
        """Непрерывный расчет в отдельном потоке"""
        while self.running:
            self.calculate_step()
            time.sleep(self.dt)
    
    def calculate_step(self):
        """Один шаг расчета (точная реализация MATLAB кода)"""
        i = len(self.t)
        
        # 1. Регулятор уровня воды (как в MATLAB)
        eps = self.M_v[-1] - self.M_v_z
        self.sum += eps
        G_v = self.G_v_n - self.Kp * (eps + self.sum * self.dt / self.Ti)
        
        # Ограничение на расход воды (как в MATLAB)
        if G_v <= 0:
            G_v = 0
        if G_v >= 5:
            G_v = 5
        
        # 2. Определение давления пара по температуре воды (как в MATLAB)
        current_p = float(self.p_interp(self.t_v[-1]))
        
        # 3. Измеренное значение давления (как в MATLAB)
        current_pi = self.pi[-1] + self.dt * ((current_p - self.pi[-1]) / self.Td)
        
        # 4. Регулятор давления (как в MATLAB)
        eps2 = -current_pi + self.p_z
        self.sum2 += eps2
        mu2_ = self.mu2_n + self.Kp2 * (eps2 + self.sum2 * self.dt / self.Ti2)
        
        # Ограничение на проводимость клапана (как в MATLAB)
        if mu2_ < 0:
            mu2_ = 0
        
        if i == 1:
            self.mu2_old = mu2_
        
        # 5. Реальная проводимость клапана (как в MATLAB)
        mu2 = self.mu2_old + self.dt * ((mu2_ - self.mu2_old) / self.Tim)
        self.mu2_old = mu2
        
        # 6. Решение уравнений модели (как в MATLAB)
        V_p = self.V_0 - self.M_v[-1] / self.ro_v
        M_p_new = current_p * V_p * self.M / (self.R * (self.t_v[-1] + 273))
        
        if self.p_pot > current_p:
            G_p_new = 0
        else:
            G_p_new = self.mu1 * np.sqrt(current_p**2 - self.p_pot**2)
        
        G_pi = G_p_new + (M_p_new - self.M_p[-1]) / self.dt
        if G_pi <= 0:
            G_pi = 0
        
        M_v_new = self.M_v[-1] + self.dt * (G_v - G_pi)
        
        G_sm = mu2 * np.sqrt(self.p_t**2 + self.p_k**2)
        if self.p_t < self.p_k:
            G_sm = 0
        
        # 7. Температура в камере сгорания (как в MATLAB)
        t_k_new = (self.K * self.F * self.t_v[-1] + G_sm * (self.c_k * self.t_t_vx + self.r_t)) / (self.K * self.F + G_sm * self.c_k)
        
        # 8. Температура воды (как в MATLAB)
        t_v_new = self.t_v[-1] + self.dt * (
            self.K * self.F * (t_k_new - self.t_v[-1]) - 
            G_v * self.c_v * (self.t_v[-1] - self.t_v_vx) - 
            G_pi * self.Lamda
        ) / (self.c_v * M_v_new)
        
        # Обновление данных
        self.t.append(self.t[-1] + self.dt)
        self.t_v.append(float(t_v_new))
        self.t_k.append(float(t_k_new))
        self.p.append(float(current_p))
        self.M_v.append(float(M_v_new))
        self.M_p.append(float(M_p_new))
        self.G_p.append(float(G_p_new))
        self.pi.append(float(current_pi))
        
        # Ограничение истории (последние 1000 точек)
        if len(self.t) > 1000:
            self.t = self.t[-1000:]
            self.t_v = self.t_v[-1000:]
            self.t_k = self.t_k[-1000:]
            self.p = self.p[-1000:]
            self.M_v = self.M_v[-1000:]
            self.M_p = self.M_p[-1000:]
            self.G_p = self.G_p[-1000:]
            self.pi = self.pi[-1000:]
    
    def get_current_data(self):
        """Текущие данные для отображения"""
    
        return {
            'temperature_water': round(float(self.t_v[-1]), 2),
            'temperature_combustion': round(float(self.t_k[-1]), 2),
            'pressure': round(float(self.p[-1]) / 1000, 2),  # Па -> кПа
            'measured_pressure': round(float(self.pi[-1]) / 1000, 2),  # Па -> кПа
            'water_mass': round(float(self.M_v[-1]), 2),
            'pressure_setpoint': round(float(self.p_z) / 1000, 2),  # Па -> кПа
            'water_level_setpoint': float(self.M_v_z),
            'system_time': datetime.now().strftime('%H:%M:%S'),
            'weather': '+10°C',
    }
    
    def get_chart_data(self):
        """Данные для графиков с оптимизацией"""
        # Берем последние 1000 точек
        time_data = self.t[-1000:]
        t_v_data = self.t_v[-1000:]
        t_k_data = self.t_k[-1000:]
        p_data = [x / 1000 for x in self.p[-1000:]]  # Па -> кПа
        pi_data = [x / 1000 for x in self.pi[-1000:]]  # Па -> кПа
        M_v_data = self.M_v[-1000:]
        
        # Если данных больше 200 точек, прореживаем для отображения
        if len(time_data) > 200:
            step = len(time_data) // 200
            time_data = time_data[::step]
            t_v_data = t_v_data[::step]
            t_k_data = t_k_data[::step]
            p_data = p_data[::step]
            pi_data = pi_data[::step]
            M_v_data = M_v_data[::step]
        
        return {
            'time': [round(float(x), 1) for x in time_data],
            'temperature_water': [float(x) for x in t_v_data],
            'temperature_combustion': [float(x) for x in t_k_data],
            'pressure': [float(x) for x in p_data],
            'measured_pressure': [float(x) for x in pi_data],
            'water_mass': [float(x) for x in M_v_data]
        }
    
    def stop(self):
        self.running = False