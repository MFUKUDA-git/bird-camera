import time
import cv2
import threading
import queue
import subprocess
import io
from collections import deque
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder

# ==========================================
# 1. カスタム出力クラス (io.BufferedIOBaseを継承)
# ==========================================
class BirdCamOutput(io.BufferedIOBase):
    def __init__(self, ffmpeg_proc, pre_rec_seconds=3, bitrate=2000000):
        super().__init__()
        self.ffmpeg_proc = ffmpeg_proc
        self.max_bytes = (bitrate // 8) * pre_rec_seconds
        self.buffer = deque()
        self.buffer_size = 0
        self.lock = threading.Lock()
        
        self.is_recording = False
        self.record_file = None
        self.record_end_time = 0
        self.raw_filepath = ""
        
        # ウォッチドッグ用の最終書き込み時刻
        self.last_stream_time = time.time()
        self.stream_failed = False

    def writable(self):
        return True

    def write(self, data):
        # 1. YouTube Live用のFFmpegへ書き込み
        if not self.stream_failed and self.ffmpeg_proc.stdin:
            try:
                self.ffmpeg_proc.stdin.write(data)
                self.last_stream_time = time.time()
            except Exception as e:
                print(f"[Error] FFmpeg write failed: {e}")
                self.stream_failed = True
                
        # 2. ローカル録画用リングバッファ
        with self.lock:
            if not self.is_recording:
                self.buffer.append(data)
                self.buffer_size += len(data)
                while self.buffer_size > self.max_bytes and len(self.buffer) > 1:
                    popped = self.buffer.popleft()
                    self.buffer_size -= len(popped)
            else:
                if self.record_file:
                    self.record_file.write(data)
                if time.time() > self.record_end_time:
                    self.stop_recording()
        
        return len(data)

    def flush(self):
        if not self.stream_failed and self.ffmpeg_proc.stdin:
            try:
                self.ffmpeg_proc.stdin.flush()
            except:
                pass

    def trigger_record(self, post_rec_seconds=5, filepath="bird_event"):
        """動体検知時に呼び出され、バッファ内容を書き出して録画を開始する"""
        with self.lock:
            if self.is_recording:
                return
            
            self.is_recording = True
            self.record_end_time = time.time() + post_rec_seconds
            self.raw_filepath = f"{filepath}.h264"
            self.record_file = open(self.raw_filepath, 'wb')
            
            # プリレック（リングバッファ）分を先頭に書き出す
            for data in self.buffer:
                self.record_file.write(data)
            self.buffer.clear()
            self.buffer_size = 0
            print(f"[Record] 録画開始: {self.raw_filepath}")

    def stop_recording(self):
        """指定時間が経過したら録画を停止し、MP4へ変換する"""
        if self.record_file:
            self.record_file.close()
            self.record_file = None
            print(f"[Record] 録画終了。MP4へ変換します...")
            mp4_filepath = self.raw_filepath.replace(".h264", ".mp4")
            threading.Thread(target=self._mux_to_mp4, args=(self.raw_filepath, mp4_filepath)).start()
        self.is_recording = False

    def _mux_to_mp4(self, raw_file, mp4_file):
        """別スレッドでFFmpegを使い軽量にコンテナ変換 (-c copy)"""
        cmd = ['/usr/bin/ffmpeg', '-y', '-i', raw_file, '-c:v', 'copy', mp4_file]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[Record] MP4保存完了: {mp4_file}")


# ==========================================
# 2. YOLO非同期連携用ワーカー
# ==========================================
yolo_queue = queue.Queue(maxsize=10)

def yolo_worker():
    while True:
        frame = yolo_queue.get()
        if frame is None:
            break
        print("[AI] YOLO 推論プロセスへ画像を転送しました")
        yolo_queue.task_done()

threading.Thread(target=yolo_worker, daemon=True).start()


# ==========================================
# 3. メイン処理 (再起動ループ対応)
# ==========================================
def run_pipeline():
    """1回分の配信・監視パイプラインを構築して実行する"""
    youtube_stream_key = "sz5u-z5dh-w71k-t5ee-36q9"
    youtube_url = f"rtmp://a.rtmp.youtube.com/live2/{youtube_stream_key}"
    
    ffmpeg_cmd = [
        '/usr/bin/ffmpeg', '-loglevel', 'warning', '-y',
        '-thread_queue_size', '4096',
        '-f', 'h264', '-i', '-',
        '-c:v', 'copy',
        '-f', 'flv', 
        '-rtmp_buffer', '2000', '-rtmp_live', 'live',
        '-rw_timeout', '5000000',
        youtube_url
    ]
    
    ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    output_handler = BirdCamOutput(ffmpeg_proc, pre_rec_seconds=3)

    picam2 = Picamera2()
    
    try:
        config = picam2.create_video_configuration(
            main={"size": (1920, 1080), "format": "RGB888"},
            lores={"size": (640, 480), "format": "YUV420"}
        )
        picam2.configure(config)
        picam2.start()
        
        # io.BufferedIOBase を継承しているため、そのまま渡すことが可能
        picam2.start_recording(H264Encoder(bitrate=2000000), output_handler)

        bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=25, detectShadows=False)
        roi_x, roi_y, roi_w, roi_h = 200, 150, 240, 240 

        print("監視・配信を開始しました")

        while True:
            # --- ウォッチドッグ (ヘルスチェック) ---
            now = time.time()
            if ffmpeg_proc.poll() is not None:
                print("[Watchdog] FFmpeg process terminated unexpectedly.")
                break
            if output_handler.stream_failed:
                print("[Watchdog] FFmpeg stream write failed.")
                break
            if now - output_handler.last_stream_time > 60:
                print("[Watchdog] Camera stream frozen (Write timeout). Forcing restart...")
                break

            # --- OpenCV 動体検知処理 ---
            frame = picam2.capture_array("lores")
            crop_frame = frame[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
            gray = cv2.cvtColor(crop_frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            fg_mask = bg_subtractor.apply(gray)
            thresh = cv2.threshold(fg_mask, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                if cv2.contourArea(contour) > 500:
                    if not output_handler.is_recording:
                        print("🐦 動体を検知！")
                        output_handler.trigger_record(post_rec_seconds=5, filepath=f"event_{int(now)}")
                        if not yolo_queue.full():
                            yolo_queue.put(frame.copy())
                    break
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Pipeline Exception: {e}")
    finally:
        print("パイプラインをシャットダウン中...")
        try:
            picam2.stop_recording()
        except: pass
        
        try:
            picam2.stop()
        except: pass
        
        try:
            picam2.close()
        except: pass

        if ffmpeg_proc:
            if ffmpeg_proc.stdin:
                try: ffmpeg_proc.stdin.close()
                except: pass
            try: ffmpeg_proc.kill()
            except: pass
            try: ffmpeg_proc.wait()
            except: pass

def main():
    while True:
        try:
            print(f"Starting birdcam pipeline at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            run_pipeline()
            print("Pipeline stopped. Restarting in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("ユーザー操作により完全終了します。")
            yolo_queue.put(None)
            break
        except Exception as e:
            print(f"Unexpected error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()