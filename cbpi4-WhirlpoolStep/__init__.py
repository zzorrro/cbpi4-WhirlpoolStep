import asyncio
import logging
from datetime import datetime
import time
from cbpi.api import *
from cbpi.api.step import CBPiStep, StepResult
from cbpi.api.timer import Timer
from cbpi.api.dataclasses import NotificationType

@parameters([
    Property.Number(label="Target Temp", description="Температура, до которой нужно охладить сусло (например, 85)", configurable=True),
    Property.Number(label="Hold Time", description="Время выдержки в минутах после достижения температуры (например, 15)", configurable=True),
    Property.Sensor(label="Sensor", description="Датчик температуры в котле"),
    Property.Kettle(label="Kettle", description="Варочный котел"),
    Property.Actor(label="Cooling Actor", description="Клапан, который включает охлаждение")
])
class WhirlpoolStep(CBPiStep):

    async def on_timer_done(self, timer):
        """Действие при завершении таймера выдержки"""
        self.summary = ""
        self.cbpi.notify(self.name, 'Вирпул завершен', NotificationType.SUCCESS)
        await self.next()

    async def on_timer_update(self, timer, seconds):
        """Обновление отображения таймера в интерфейсе"""
        self.summary = f"{Timer.format_time(seconds)}"
        await self.push_update()

    async def on_start(self):
        """Инициализация при запуске шага (в стиле BM_Steps)"""
        # 1. Явное получение параметров, как в BM_MashStep
        self.port = str(self.cbpi.static_config.get('port', 8000))
        self.kettle = self.get_kettle(self.props.get("Kettle", None))
        self.sensor = self.props.get("Sensor", None)
        self.cooling_actor = self.props.get("Cooling Actor", None)
        
        self.target_temp = float(self.props.get("Target Temp", 85))
        self.hold_time = int(self.props.get("Hold Time", 15))
        self.hold_time_seconds = self.hold_time * 60
        
        self.cooling_active = True
        
        # 2. Безопасность: отключаем целевую температуру котла, чтобы PID-нагрев не мешал охлаждению
        if self.kettle is not None:
            self.kettle.target_temp = 0 

        # 3. Инициализация таймера
        if self.timer is None:
            self.timer = Timer(self.hold_time_seconds, on_update=self.on_timer_update, on_done=self.on_timer_done)

        # 4. Автоматическое включение охлаждения при старте (наш аналог AutoMode для охлаждения)
        if self.cooling_actor is not None:
            await self.actor_on(self.cooling_actor)
            
        self.summary = f"Охлаждение до {self.target_temp}°C..."
        self.cbpi.notify(self.name, f'Охлаждение до {self.target_temp}°C', NotificationType.INFO)
        await self.push_update()

    async def on_stop(self):
        """Действие при ручной остановке шага (безопасность)"""
        await self.timer.stop()
        self.summary = ""
        # Гарантированно выключаем охлаждение при остановке шага
        if self.cooling_actor is not None:
            await self.actor_off(self.cooling_actor)
        await self.push_update()

    async def reset(self):
        """Сброс состояния шага"""
        self.hold_time = int(self.props.get("Hold Time", 15))
        self.timer = Timer(self.hold_time * 60, on_update=self.on_timer_update, on_done=self.on_timer_done)
        self.cooling_active = True

    async def run(self):
        """Основной цикл выполнения шага (в стиле BM_Cooldown)"""
        while self.running == True:
            await asyncio.sleep(1)
            
            # Получаем текущее значение температуры
            sensor_data = self.get_sensor_value(self.sensor)
            if sensor_data and "value" in sensor_data:
                current_temp = float(sensor_data.get("value"))
                
                # Если охлаждение активно и мы достигли целевой температуры
                if self.cooling_active and current_temp <= self.target_temp:
                    self.cooling_active = False
                    
                    # Выключаем клапан охлаждения
                    if self.cooling_actor is not None:
                        await self.actor_off(self.cooling_actor)
                    
                    self.summary = f"Выдержка {self.hold_time} мин..."
                    self.cbpi.notify(self.name, f'Температура {self.target_temp}°C достигнута. Охлаждение выключено. Началась выдержка.', NotificationType.INFO)
                    
                    # Запускаем таймер выдержки
                    if self.timer.is_running is not True:
                        self.timer.start()
                        self.timer.is_running = True
                        
            await self.push_update()

        return StepResult.DONE


def setup(cbpi):
    '''
    Этот метод вызывается сервером CBPI4 при запуске.
    Здесь мы регистрируем наш новый плагин.
    '''
    cbpi.plugin.register("WhirlpoolStep", WhirlpoolStep)