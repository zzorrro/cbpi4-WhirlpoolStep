import asyncio
import logging
from datetime import datetime
import time
from cbpi.api import *
from cbpi.api.step import CBPiStep, StepResult
from cbpi.api.timer import Timer
from cbpi.api.dataclasses import NotificationType

@parameters([
    Property.Number(label="Target Temp", description="Target temperature to cool the wort to (e.g., 85)", configurable=True),
    Property.Number(label="Hold Time", description="Hold time in minutes after reaching target temperature (e.g., 15)", configurable=True),
    Property.Sensor(label="Sensor", description="Temperature sensor in the kettle"),
    Property.Kettle(label="Kettle", description="Boiling kettle"),
    Property.Actor(label="Cooling Actor", description="Actor/Valve that triggers cooling")
])
class WhirlpoolStep(CBPiStep):

    @action("START TIMER", [])
    async def start_timer(self):
        if self.timer.is_running is not True:
            self.cbpi.notify(self.name, 'Timer started', NotificationType.INFO)
            self.timer.start()
            self.timer.is_running = True
        else:
            self.cbpi.notify(self.name, 'Timer is already running', NotificationType.WARNING)

    @action("ADD 5 MINUTES TO TIMER", [])
    async def add_timer(self):
        if self.timer.is_running == True:
            self.cbpi.notify(self.name, '5 Minutes added', NotificationType.INFO)
            await self.timer.add(300)       
        else:
            self.cbpi.notify(self.name, 'Timer must be running to add time', NotificationType.WARNING)

    async def on_timer_done(self, timer):
        """Действие при завершении таймера выдержки"""
        self.summary = ""
        # Гарантированно выключаем охлаждение при завершении шага
        if self.cooling_actor is not None:
            await self.actor_off(self.cooling_actor)
        self.cbpi.notify(self.name, 'Whirlpool completed', NotificationType.SUCCESS)
        await self.next()

    async def on_timer_update(self, timer, seconds):
        """Обновление отображения таймера в интерфейсе (только время)"""
        self.summary = Timer.format_time(seconds)
        await self.push_update()

    async def on_start(self):
        """Инициализация при запуске шага (в стиле BM_Steps)"""
        self.port = str(self.cbpi.static_config.get('port', 8000))
        
        # 1. Явное получение параметров (обязательные через атрибут, опциональные через get)
        self.kettle = self.get_kettle(self.props.Kettle)
        self.sensor = self.props.Sensor
        self.cooling_actor = self.props.get("Cooling Actor", None)
        
        self.target_temp = float(self.props.get("Target Temp", 85))
        self.hold_time = int(self.props.get("Hold Time", 15))
        self.hold_time_seconds = self.hold_time * 60
        
        self.cooling_active = True
        
        # 2. Устанавливаем целевую температуру котла для отображения (например, 85°C)
        # ВАЖНО: Мы НЕ вызываем setAutoMode(True), поэтому PID не активируется
        # Охлаждение управляется только через cooling_actor
        if self.kettle is not None:
            self.kettle.target_temp = int(self.target_temp)
            logging.info(f"Kettle target temp set to {self.target_temp}°C (PID not activated)")

        # 3. Инициализация таймера (пока не запускаем его)
        if self.timer is None:
            self.timer = Timer(self.hold_time_seconds, on_update=self.on_timer_update, on_done=self.on_timer_done)

        # 4. Автоматическое включение актора охлаждения при старте шага
        if self.cooling_actor is not None:
            await self.actor_on(self.cooling_actor)
            
        self.summary = f"Cooling to {self.target_temp}°C..."
        self.cbpi.notify(self.name, f'Cooling to {self.target_temp}°C', NotificationType.INFO)
        await self.push_update()

    async def on_stop(self):
        """Действие при ручной остановке шага (безопасность)"""
        await self.timer.stop()
        self.summary = ""
        # Сбрасываем целевую температуру котла в 0 при остановке
        if self.kettle is not None:
            self.kettle.target_temp = 0
        # Гарантированно выключаем охлаждение при принудительной остановке
        if self.cooling_actor is not None:
            await self.actor_off(self.cooling_actor)
        await self.push_update()

    async def reset(self):
        """Сброс состояния шага при перезапуске"""
        self.hold_time = int(self.props.get("Hold Time", 15))
        self.timer = Timer(self.hold_time * 60, on_update=self.on_timer_update, on_done=self.on_timer_done)
        self.cooling_active = True

    async def run(self):
        """Основной цикл выполнения шага (в стиле BM_Cooldown)"""
        while self.running == True:
            await asyncio.sleep(1)
            
            # Получаем текущее значение температуры с датчика
            sensor_data = self.get_sensor_value(self.sensor)
            if sensor_data and "value" in sensor_data:
                current_temp = float(sensor_data.get("value"))
                
                # Если охлаждение активно и мы достигли (или прошли) целевую температуру
                if self.cooling_active and current_temp <= self.target_temp:
                    self.cooling_active = False
                    
                    # Выключаем клапан/актор охлаждения
                    if self.cooling_actor is not None:
                        await self.actor_off(self.cooling_actor)
                    
                    # Простое уведомление о достижении температуры (без расчетного времени)
                    self.cbpi.notify(
                        self.name, 
                        f'Target temp {self.target_temp}°C reached. Cooling off. Hold time started.', 
                        NotificationType.INFO
                    )
                    
                    # Запускаем таймер выдержки, если он еще не запущен
                    if self.timer.is_running is not True:
                        self.timer.start()
                        self.timer.is_running = True
                        
            await self.push_update()

        return StepResult.DONE


def setup(cbpi):
    '''
    Этот метод вызывается сервером CBPI4 при запуске.
    Здесь мы регистрируем наш новый плагин в системе.
    '''
    cbpi.plugin.register("WhirlpoolStep", WhirlpoolStep)
