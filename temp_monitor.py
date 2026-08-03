import time
from datetime import datetime
from gpiozero import OutputDevice, CPUTemperature

# ハードウェア設定 (setup_record.md に準拠)
FAN_PIN = 14
fan = OutputDevice(FAN_PIN)
cpu = CPUTemperature()

# 設定値
LOG_FILE = "/home/msofk/bird-camera/cpu_temp.log"
TEMP_ON = 75.0   # ファン起動閾値（75℃）
TEMP_OFF = 60.0  # ファン停止閾値（60℃：頻繁なオンオフを防ぐ余裕を持たせる）
CHECK_INTERVAL = 10  # 温度チェックの間隔（秒）

def log_temp(temp, status_msg=""):
    """温度とステータスをログファイルに追記する関数"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"{timestamp} - CPU温度: {temp:.1f}℃ {status_msg}\n"
    
    with open(LOG_FILE, 'a') as f:
        f.write(log_line)

fan_is_on = False
log_temp(cpu.temperature, "[OS起動] 温度監視とファン制御を開始しました")

try:
    while True:
        current_temp = cpu.temperature
        
        # 閾値判定とファン制御
        if current_temp >= TEMP_ON and not fan_is_on:
            fan.on()
            fan_is_on = True
            log_temp(current_temp, "★[ALERT] 75℃に到達しました。ファンを起動します。")
            
        elif current_temp <= TEMP_OFF and fan_is_on:
            fan.off()
            fan_is_on = False
            log_temp(current_temp, "☆[INFO] 温度が低下しました。ファンを停止します。")
            
        else:
            # 状態変化がなくても温度推移がわかるように記録
            log_temp(current_temp)
            
        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    fan.off()
    log_temp(cpu.temperature, "[システム停止] 監視を終了します")