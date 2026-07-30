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