import time
from gpiozero import OutputDevice

# ファン制御用のGPIOピン番号 (GPIO 14)
FAN_PIN = 14

# OutputDeviceとしてピンを初期化
fan = OutputDevice(FAN_PIN)

print("=== ファン常時運転モード ===")
print("停止するには Enter キーを押すか、Ctrl+C を入力してください。")

try:
    fan.on()
    print("ファンをONにしました。")

    # Enterが押されるまで待機
    input("停止するまでファンは動作します。Enterで停止: ")

    print("停止指示を受け取りました。ファンをOFFにします...")

except KeyboardInterrupt:
    print("\nKeyboardInterruptを検知しました。ファンをOFFにします...")

finally:
    fan.off()
    print("ファンを停止しました。")
    print("=== 終了 ===")
