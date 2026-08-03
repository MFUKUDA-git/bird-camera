import cv2
import io
import pandas as pd
import matplotlib
# Flaskなどのサーバー環境でグラフを描画するための必須設定（GUIを出さない）
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from flask import Flask, Response, render_template_string, send_file
from picamera2 import Picamera2

app = Flask(__name__)
picam2 = Picamera2()

# カメラの設定
config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(config)
picam2.start()

# ダッシュボード用のHTMLテンプレート
# CSS (flexbox) を使って映像とグラフを横並び（スマホ等の場合は縦並び）に配置します
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Bird Camera Dashboard</title>
    <style>
        body { font-family: sans-serif; text-align: center; background-color: #f4f4f9; color: #333; }
        .container { display: flex; justify-content: center; align-items: flex-start; gap: 20px; padding: 20px; flex-wrap: wrap; }
        .box { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { margin-top: 20px; }
        img { max-width: 100%; height: auto; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Bird Camera Dashboard</h1>
    <div class="container">
        <!-- 左側：カメラ映像 -->
        <div class="box">
            <h2>Live View</h2>
            <img src="{{ url_for('video_feed') }}">
        </div>
        
        <!-- 右側：システムグラフ -->
        <div class="box">
            <h2>System Status</h2>
            <p style="font-size: 0.8em; color: gray;">※グラフは30秒ごとに自動更新されます</p>
            <img id="graph" src="{{ url_for('system_graph') }}" style="width: 500px;">
        </div>
    </div>

    <!-- グラフ画像だけを定期的にリロードするJavaScript -->
    <script>
        setInterval(() => {
            // URLの末尾に時刻を付けて、ブラウザのキャッシュ（古い画像）を無視させる
            document.getElementById('graph').src = "{{ url_for('system_graph') }}?" + new Date().getTime();
        }, 30000); // 30000ミリ秒 = 30秒
    </script>
</body>
</html>
"""

def generate_frames():
    """カメラ映像を生成する関数"""
    while True:
        frame = picam2.capture_array("main")
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    """トップページにアクセスされたらHTMLを表示"""
    return render_template_string(HTML_PAGE)

@app.route('/video_feed')
def video_feed():
    """映像ストリームの配信URL"""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/graph')
def system_graph():
    """アクセスされるたびに最新のCSVを読み込んでグラフ画像を返す"""
    LOG_FILE = "/home/msofk/bird-camera/system_stats.csv"
    try:
        df = pd.read_csv(LOG_FILE)
        
        # データが多すぎる場合は直近の300件（約50分間）などに絞る（見やすくするため）
        df = df.tail(300) 
        
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        
        fig, ax1 = plt.subplots(figsize=(7, 4))
        
        # 温度 (赤)
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Temperature (C)', color='tab:red')
        ax1.plot(df['Timestamp'], df['Temperature(C)'], color='tab:red')
        ax1.tick_params(axis='y', labelcolor='tab:red')
        
        # CPU (青)
        ax2 = ax1.twinx()  
        ax2.set_ylabel('CPU Usage (%)', color='tab:blue')
        ax2.plot(df['Timestamp'], df['CPU(%)'], color='tab:blue', alpha=0.5)
        ax2.tick_params(axis='y', labelcolor='tab:blue')
        
        # ファン状態 (オレンジ背景)
        if 'Fan_ON' in df.columns:
            fan_on_periods = df[df['Fan_ON'] == 1]
            for _, row in fan_on_periods.iterrows():
                ax1.axvspan(row['Timestamp'], row['Timestamp'], color='orange', alpha=0.3)
                
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        fig.autofmt_xdate()
        fig.tight_layout()
        
        # 画像をメモリ上で作成して直接ブラウザに送信
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png')
        img_buffer.seek(0)
        plt.close(fig) # メモリリークを防ぐために必ず閉じる
        
        return send_file(img_buffer, mimetype='image/png')
        
    except Exception as e:
        return f"Graph Generation Error: {e}", 500

if __name__ == '__main__':
    print("=== ダッシュボードサーバー起動 ===")
    print("ブラウザで http://<Raspberry PiのIPアドレス>:5000 にアクセスしてください")
    app.run(host='0.0.0.0', port=5000)