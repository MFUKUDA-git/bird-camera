from gpiozero import OutputDevice
import time

# ファン制御用のGPIOピン番号 (GPIO 14)
FAN_PIN = 14

# OutputDeviceとしてピンを初期化
fan = OutputDevice(FAN_PIN)

print("=== ファン制御テスト開始 ===")

try:
    print("ファンをONにします... (5秒間)")
    fan.on()       # GPIO14をHIGH(3.3V)にする
    time.sleep(5)  # 5秒待機

    print("ファンをOFFにします...")
    fan.off()      # GPIO14をLOW(0V)にする
    time.sleep(2)  # 2秒待機

    print("テストが正常に完了しました！")

except KeyboardInterrupt:
    # 実行中に Ctrl+C が押された場合の処理
    print("\nテストを中断しました。")
finally:
    # プログラム終了時は必ずファンを止める
    fan.off()
    print("=== テスト終了 ===")