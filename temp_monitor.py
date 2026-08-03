import time
import csv
import os
import psutil
from datetime import datetime
from gpiozero import OutputDevice, CPUTemperature

# ハードウェア設定
FAN_PIN = 14
fan = OutputDevice(FAN_PIN)
cpu = CPUTemperature()

# 設定値
LOG_FILE = "/home/msofk/bird-camera/system_stats.csv"
TEMP_ON = 75.0
TEMP_OFF = 60.0
CHECK_INTERVAL = 10

def log_data(temp, cpu_percent, mem_percent, fan_is_on):
    """CSV形式でデータを記録する関数"""
    file_exists = os.path.isfile(LOG_FILE)
    
    with open(LOG_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        # ファイルが新規作成された場合はヘッダー（列名）を書き込む
        if not file_exists:
            writer.writerow(['Timestamp', 'Temperature(C)', 'CPU(%)', 'Memory(%)', 'Fan_ON'])
            
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        fan_status = 1 if fan_is_on else 0
        writer.writerow([timestamp, f"{temp:.1f}", f"{cpu_percent:.1f}", f"{mem_percent:.1f}", fan_status])

fan_is_on = False

try:
    while True:
        current_temp = cpu.temperature
        # CPUとメモリの使用率を取得
        cpu_usage = psutil.cpu_percent(interval=None)
        mem_usage = psutil.virtual_memory().percent
        
        # ファン制御
        if current_temp >= TEMP_ON and not fan_is_on:
            fan.on()
            fan_is_on = True
        elif current_temp <= TEMP_OFF and fan_is_on:
            fan.off()
            fan_is_on = False
            
        # データの記録
        log_data(current_temp, cpu_usage, mem_usage, fan_is_on)
        
        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    fan.off()