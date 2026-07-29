from picamera2 import Picamera2
import time

print("=== カメラ撮影テスト開始 ===")

try:
    # カメラの初期化
    picam2 = Picamera2()
    picam2.start()
    print("カメラを起動しました。明るさの自動調整のため2秒待機します...")
    
    # オートフォーカスや露出調整が安定するまで少し待つ
    time.sleep(2)

    # 画像の保存ファイル名
    filename = "test_photo.jpg"
    
    # 撮影と保存
    picam2.capture_file(filename)
    print(f"撮影成功！画像を保存しました: {filename}")

except Exception as e:
    print(f"エラーが発生しました: {e}")
finally:
    # 確実にカメラを終了する
    if 'picam2' in locals():
        picam2.stop()
        print("カメラを停止しました。")
    print("=== テスト終了 ===")