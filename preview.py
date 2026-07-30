import cv2
from flask import Flask, Response
from picamera2 import Picamera2

app = Flask(__name__)
picam2 = Picamera2()

# カメラの設定（プレビュー用に扱いやすい解像度に設定）
config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(config)
picam2.start()

def generate_frames():
    while True:
        # カメラから最新の画像配列を取得
        frame = picam2.capture_array("main")
        
        # OpenCVを使ってJPEG形式に変換
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        # Webブラウザで連続表示するためのデータ形式（MJPEG）にして送信
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def video_feed():
    # ブラウザからアクセスがあったら映像データを返し続ける
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("=== プレビューサーバー起動 ===")
    print("ブラウザで http://<Raspberry PiのIPアドレス>:5000 にアクセスしてください")
    print("終了するには Ctrl+C を押してください")
    # すべてのIPからのアクセスを許可してポート5000で待機
    app.run(host='0.0.0.0', port=5000)