無事にカメラでの撮影まで成功したとのこと、素晴らしい進捗です！ハードウェアとソフトウェアが完全に連携しましたね。

今後の再構築やバックアップのために、ここまでのセットアップ手順を（GitHub Copilotの試行錯誤部分を除いて）整理しました。マークダウン形式で出力しますので、このテキストをコピーして `setup_record.md` などの名前でプロジェクトフォルダ内に保存しておくと便利です。

---

# 鳥判定カメラ プロジェクト - 環境構築・セットアップ記録

## 1. 前提条件（初期状態）

* **ハードウェア**: Raspberry Pi 4B, カメラモジュール3, 自作FETファン制御回路 (GPIO 14, 5V, GND)
* **OS**: Raspberry Pi OS Lite (64-bit)
* **ネットワーク**: 無線LAN接続済み、SSHログイン可能
* **クライアント**: Windows 10/11環境, VS Codeインストール済み
* **アカウント**: GitHubアカウント作成済み

---

## 2. Windows側（VS Code）のセットアップ

### 2.1. Remote-SSH 拡張機能の導入と設定

1. VS Codeの拡張機能から `Remote - SSH` (Microsoft製) をインストール。
2. `Ctrl + Shift + P` でコマンドパレットを開き、`Remote-SSH: Open SSH Configuration File...` を選択。
3. `config` ファイルに以下の接続設定を追加。
```text
Host birdcam
    HostName birdcam.local
    User msofk

```


4. リモートエクスプローラー（または左下の `><` アイコン）から `birdcam` に接続し、パスワードを入力。
5. OSの選択ダイアログが出た場合は `Linux` を選択。

---

## 3. Raspberry Pi側のセットアップ

### 3.1. 作業用フォルダの作成

VS Codeのターミナル（SSH接続先）で以下のコマンドを実行し、プロジェクトフォルダを作成してVS Codeで開く。

```bash
mkdir bird-camera
cd bird-camera

```

※以降の作業は、VS Codeで `/home/msofk/bird-camera` を開いた状態のターミナルで実施。

### 3.2. Gitのインストールと初期設定

OS LiteにはGitが未搭載のためインストールし、ユーザー情報を設定する。

```bash
sudo apt update
sudo apt install git -y
git config --global user.name "MFUKUDA-git"
git config --global user.email "自身のGitHub登録メールアドレス"

```

### 3.3. GitHubとのSSH連携設定

安全な通信のためのSSH鍵を作成し、GitHubに登録する。

```bash
# SSH鍵の生成（質問はすべてEnterでスキップ）
ssh-keygen -t ed25519 -C "自身のGitHub登録メールアドレス"

# 公開鍵の表示（表示された ssh-ed25519 から始まる1行をコピー）
cat ~/.ssh/id_ed25519.pub

```

1. コピーした鍵を GitHubの `Settings` > `SSH and GPG keys` > `New SSH key` に登録。
2. 接続テストを実施。
```bash
ssh -T git@github.com

```


※ `Hi MFUKUDA-git! ...` と表示されれば成功。

### 3.4. GitHubリポジトリの作成と初回Push

1. GitHubのWeb上で空のリポジトリ `bird-camera` を作成（README等は追加しない）。
2. Raspberry Pi側で初期化とPushを行う。
```bash
git init
echo "# Bird Camera Project" > README.md
git add README.md
git commit -m "first commit"
git branch -M main
git remote add origin git@github.com:MFUKUDA-git/bird-camera.git
git push -u origin main

```



### 3.5. Python仮想環境の構築と `.gitignore` の設定

システム環境を汚さずに開発するため `venv` を作成する。**※カメラモジュールを使うため `--system-site-packages` が必須。**

```bash
# 仮想環境の作成と有効化
python3 -m venv --system-site-packages venv
source venv/bin/activate

# .gitignoreの作成（不要ファイルのPush防止）
echo "venv/" > .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore

# 変更をコミットしてPush
git add .gitignore
git commit -m "add .gitignore"
git push

```

※以降のPython作業は、ターミナルで `source venv/bin/activate` を実行し `(venv)` が表示された状態で行う。

### 3.6. カメラ用ライブラリのインストール

OS Liteにはカメラ機能が同梱されていないため、`picamera2` 関連を追加インストールする。

```bash
sudo apt update
sudo apt install libcamera-apps python3-picamera2 -y

```

---

## 4. ハードウェア動作テスト用スクリプト

### 4.1. ファン制御テスト (`fan_test.py`)

GPIO 14を使用し、ファンを5秒間オンにするテスト。

```python
from gpiozero import OutputDevice
import time

FAN_PIN = 14
fan = OutputDevice(FAN_PIN)

print("=== ファン制御テスト開始 ===")
try:
    print("ファンをONにします... (5秒間)")
    fan.on()
    time.sleep(5)
    print("ファンをOFFにします...")
    fan.off()
    time.sleep(2)
    print("テストが正常に完了しました！")
except KeyboardInterrupt:
    print("\nテストを中断しました。")
finally:
    fan.off()
    print("=== テスト終了 ===")

```

### 4.2. カメラ撮影テスト (`camera_test.py`)

Picamera2を使用し、写真を1枚撮影して保存するテスト。

```python
from picamera2 import Picamera2
import time

print("=== カメラ撮影テスト開始 ===")
try:
    picam2 = Picamera2()
    picam2.start()
    print("カメラを起動しました。明るさの自動調整のため2秒待機します...")
    time.sleep(2)

    filename = "test_photo.jpg"
    picam2.capture_file(filename)
    print(f"撮影成功！画像を保存しました: {filename}")

except Exception as e:
    print(f"エラーが発生しました: {e}")
finally:
    if 'picam2' in locals():
        picam2.stop()
        print("カメラを停止しました。")
    print("=== テスト終了 ===")

```

### 4.3. カメラ設置調整用リアルタイムプレビュー (`preview.py`)

カメラのアングルやピントなどの設置調整を行うため、FlaskおよびOpenCVを用いてブラウザからリアルタイムで映像を確認できるWebサーバーを起動するスクリプト。

#### 必要なライブラリのインストール
```bash
pip install flask opencv-python-headless
```

#### スクリプト内容 (`preview.py`)
```python
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
```

#### 実行方法
```bash
python preview.py
```
起動後、同一ネットワークのPCやスマホなどのブラウザから `http://<Raspberry PiのIPアドレス>:5000`（例: `http://birdcam.local:5000`）にアクセスしてカメラ映像を確認します。

これまでの拡張内容を `setup_record.md` に追記するためのテキストを作成しました。

既存の `setup_record.md` の末尾に、以下のMarkdownテキストをそのままコピー＆ペーストして追加してください。

---

## 5. システム監視とファン自動制御の構築

CPU温度、CPU使用率、メモリ使用率を定期的に取得してCSVに記録し、温度に応じてファン（GPIO 14）を自動制御するバックグラウンドシステムを構築する。

### 5.1. 追加ライブラリのインストール

仮想環境（`venv`）を有効にした状態で、システム情報取得および後述のグラフ化に必要なライブラリをインストールする。

```bash
pip install psutil pandas matplotlib

```

### 5.2. 監視・制御スクリプト (`temp_monitor.py`)

プロジェクトフォルダ内に `temp_monitor.py` を作成する。75℃でファンがON、60℃でOFFになるようヒステリシスを設けている。データは `system_stats.csv` に保存される。

```python
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
        if not file_exists:
            writer.writerow(['Timestamp', 'Temperature(C)', 'CPU(%)', 'Memory(%)', 'Fan_ON'])
            
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        fan_status = 1 if fan_is_on else 0
        writer.writerow([timestamp, f"{temp:.1f}", f"{cpu_percent:.1f}", f"{mem_percent:.1f}", fan_status])

fan_is_on = False

try:
    while True:
        current_temp = cpu.temperature
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

```

### 5.3. OS起動時の自動実行設定 (systemd)

Raspberry Pi起動時に監視スクリプトがバックグラウンドで自動実行されるようにする。

1. サービスファイルの作成

```bash
sudo nano /etc/systemd/system/bird-fan.service

```

2. 以下の内容を記述して保存（仮想環境のPythonを指定）

```ini
[Unit]
Description=Bird Camera CPU Fan and Temperature Monitor
After=multi-user.target

[Service]
ExecStart=/home/msofk/bird-camera/venv/bin/python /home/msofk/bird-camera/temp_monitor.py
WorkingDirectory=/home/msofk/bird-camera
Restart=always
User=msofk

[Install]
WantedBy=multi-user.target

```

3. サービスの有効化と起動

```bash
sudo systemctl daemon-reload
sudo systemctl enable bird-fan.service
sudo systemctl start bird-fan.service

```

---

## 6. Webダッシュボードの構築

プレビュー用スクリプトを拡張し、ライブカメラ映像とシステム負荷グラフ（CSVデータから生成）を同一ブラウザ画面で確認できる統合ダッシュボードを作成する。

### 6.1. ダッシュボード用スクリプトへのアップデート (`preview.py`)

既存の `preview.py` を以下のコードで上書きする。グラフはディスクに保存せず、メモリ上で生成してブラウザに直接配信する。

```python
import cv2
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg') # GUIなし環境での描画設定
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from flask import Flask, Response, render_template_string, send_file
from picamera2 import Picamera2

app = Flask(__name__)
picam2 = Picamera2()

config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(config)
picam2.start()

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
        <div class="box">
            <h2>Live View</h2>
            <img src="{{ url_for('video_feed') }}">
        </div>
        <div class="box">
            <h2>System Status</h2>
            <p style="font-size: 0.8em; color: gray;">※グラフは30秒ごとに自動更新されます</p>
            <img id="graph" src="{{ url_for('system_graph') }}" style="width: 500px;">
        </div>
    </div>
    <script>
        setInterval(() => {
            document.getElementById('graph').src = "{{ url_for('system_graph') }}?" + new Date().getTime();
        }, 30000);
    </script>
</body>
</html>
"""

def generate_frames():
    while True:
        frame = picam2.capture_array("main")
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/graph')
def system_graph():
    LOG_FILE = "/home/msofk/bird-camera/system_stats.csv"
    try:
        df = pd.read_csv(LOG_FILE)
        df = df.tail(300) # 直近のデータのみ描画
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
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png')
        img_buffer.seek(0)
        plt.close(fig)
        
        return send_file(img_buffer, mimetype='image/png')
        
    except Exception as e:
        return f"Graph Generation Error: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

```