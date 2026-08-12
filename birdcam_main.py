#!/usr/bin/env python3
"""
birdcam_main.py

Raspberry Pi 4B（ホスト名: birdcam）向けの Picamera2 ベース野鳥カメラ基本パイプラインです。

要件:
 1. Picamera2 の H.264 メインストリームを FFmpeg に渡し、YouTube Live へ常時配信
 2. OpenCV の背景差分を使った軽量動体検知（指定領域のみ）
 3. プリレック録画（リングバッファ）で最新数秒を保持し、検知時に MP4 として保存
"""

import os
import time
import io
import subprocess
import threading
from collections import deque

import cv2
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs.fileoutput import FileOutput

# --- 設定 -----------------------------------------------------------
# YouTube のライブ配信キーは複数用意して切り替え可能にする。
# 例: 環境変数 YOUTUBE_STREAM_KEY_NAME=subako とし、対応する値を以下に設定する。
YOUTUBE_STREAM_KEY = ""
YOUTUBE_STREAM_KEY_ENV_NAME = "YOUTUBE_STREAM_KEY"
YOUTUBE_STREAM_KEY_NAME_ENV_NAME = "YOUTUBE_STREAM_KEY_NAME"
YOUTUBE_URL_TEMPLATE = "rtmp://a.rtmp.youtube.com/live2/{key}"
FFMPEG_PATH = "/usr/bin/ffmpeg"

# キー候補: そのまま環境変数で上書き可能
YOUTUBE_STREAM_KEYS = {
    "default": "",
    "subako": "",
    "mizuba": "",
}

# ストリーム設定
STREAM_BITRATE = 2000000  # 2Mbps
STREAM_RESOLUTION = (1280, 720)
STREAM_FORMAT = "RGB888"

# ローカル録画リングバッファ設定
PRE_RECORD_SECONDS = 3
POST_RECORD_SECONDS = 5
BUFFER_BUDGET_FACTOR = 1.2  # 余裕を持たせる

# 動体検知設定
LORES_RESOLUTION = (640, 480)
ROI = (160, 120, 320, 240)  # x, y, w, h
MOTION_AREA_THRESHOLD = 1200
MOTION_DETECTION_INTERVAL = 0.1
MOTION_COOLDOWN_SECONDS = 3.0
WATCHDOG_TIMEOUT_SECONDS = 60

# ファイル保存先
RECORD_DIR = "./recordings"


class RingBufferH264Output(io.BufferedIOBase):
    """H.264 バイトストリームを FFmpeg へ送りつつ、プリレック用リングバッファを保持する出力クラス。"""

    def __init__(self, ffmpeg_proc, pre_rec_seconds=PRE_RECORD_SECONDS, bitrate=STREAM_BITRATE):
        super().__init__()
        self.ffmpeg_proc = ffmpeg_proc
        self.pre_rec_seconds = pre_rec_seconds
        self.bitrate = bitrate
        self.max_bytes = int((bitrate / 8) * pre_rec_seconds * BUFFER_BUDGET_FACTOR)
        self.buffer = deque()
        self.buffer_size = 0
        self.lock = threading.Lock()

        self.is_recording = False
        self.record_file = None
        self.record_end_time = 0.0
        self.raw_filepath = None

        self.last_stream_time = time.time()
        self.stream_failed = False

    def writable(self):
        return True

    def write(self, data):
        if not data:
            return 0

        self._write_to_ffmpeg(data)
        self._handle_local_buffer(data)
        return len(data)

    def _write_to_ffmpeg(self, data):
        if self.stream_failed or self.ffmpeg_proc is None or self.ffmpeg_proc.stdin is None:
            return
        try:
            self.ffmpeg_proc.stdin.write(data)
            self.last_stream_time = time.time()
        except Exception as exc:
            print(f"[Error] FFmpeg stream write failed: {exc}")
            self.stream_failed = True

    def _handle_local_buffer(self, data):
        with self.lock:
            if self.is_recording:
                if self.record_file:
                    self.record_file.write(data)
                if time.time() >= self.record_end_time:
                    self._stop_recording_locked()
            else:
                self.buffer.append(data)
                self.buffer_size += len(data)
                while self.buffer_size > self.max_bytes and len(self.buffer) > 1:
                    removed = self.buffer.popleft()
                    self.buffer_size -= len(removed)

    def flush(self):
        if self.ffmpeg_proc and self.ffmpeg_proc.stdin:
            try:
                self.ffmpeg_proc.stdin.flush()
            except Exception:
                pass

    def trigger_record(self, event_name=None, post_seconds=POST_RECORD_SECONDS):
        """動体検知時に呼び出す。リングバッファ内容を含めて録画を開始する。"""
        with self.lock:
            if self.is_recording:
                # すでに録画中なら終了時刻を延長する
                self.record_end_time = max(self.record_end_time, time.time() + post_seconds)
                return

            os.makedirs(RECORD_DIR, exist_ok=True)
            event_name = event_name or f"event_{int(time.time())}"
            raw_filename = f"{event_name}.h264"
            self.raw_filepath = os.path.join(RECORD_DIR, raw_filename)

            self.record_file = open(self.raw_filepath, "wb")
            for chunk in self.buffer:
                self.record_file.write(chunk)

            self.buffer.clear()
            self.buffer_size = 0
            self.is_recording = True
            self.record_end_time = time.time() + post_seconds

            print(f"[Record] 録画開始: {self.raw_filepath}")

    def _stop_recording_locked(self):
        if self.record_file:
            self.record_file.close()
            self.record_file = None
            raw_file = self.raw_filepath
            mp4_file = raw_file.replace(".h264", ".mp4")
            threading.Thread(target=self._mux_to_mp4, args=(raw_file, mp4_file), daemon=True).start()
            print(f"[Record] 録画終了。MP4 変換をバックグラウンドで開始: {mp4_file}")
        self.is_recording = False

    def _mux_to_mp4(self, raw_file, mp4_file):
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i",
            raw_file,
            "-c:v",
            "copy",
            mp4_file,
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print(f"[Record] MP4 保存完了: {mp4_file}")
        except subprocess.CalledProcessError as exc:
            print(f"[Error] MP4 変換に失敗しました: {exc}")

    def close(self):
        with self.lock:
            if self.record_file:
                self.record_file.close()
                self.record_file = None
            if self.ffmpeg_proc and self.ffmpeg_proc.stdin:
                try:
                    self.ffmpeg_proc.stdin.close()
                except Exception:
                    pass
        super().close()


def _mask_stream_key(stream_key: str) -> str:
    if not stream_key:
        return "<empty>"
    if len(stream_key) <= 8:
        return "*" * len(stream_key)
    return f"{stream_key[:4]}...{stream_key[-4:]}"


def resolve_stream_key():
    """環境変数または複数の候補キーから、現在使う配信キーを決定する。"""
    alias = os.environ.get(YOUTUBE_STREAM_KEY_NAME_ENV_NAME, "default").strip().lower()
    direct_key = os.environ.get(YOUTUBE_STREAM_KEY_ENV_NAME, "").strip()

    if alias and alias in YOUTUBE_STREAM_KEYS:
        candidate = YOUTUBE_STREAM_KEYS.get(alias, "")
        if candidate:
            return alias, candidate

    if direct_key:
        return "direct", direct_key

    if alias in YOUTUBE_STREAM_KEYS:
        # 既定のキー候補がある場合はそれを用いる
        key = YOUTUBE_STREAM_KEYS.get(alias, "")
        if key:
            return alias, key

    # 互換性維持: 既に YOUTUBE_STREAM_KEY を直接設定している場合
    if YOUTUBE_STREAM_KEY:
        return "default", YOUTUBE_STREAM_KEY

    raise ValueError(
        "YouTube のストリームキーが設定されていません。"
        "YOUTUBE_STREAM_KEY または YOUTUBE_STREAM_KEY_NAME=subako/mizuba/default を設定してください。"
    )


def create_ffmpeg_process(stream_key: str):
    if not stream_key:
        raise ValueError("YouTube のストリームキーが設定されていません。環境変数 YOUTUBE_STREAM_KEY で指定してください。")
    youtube_url = YOUTUBE_URL_TEMPLATE.format(key=stream_key)
    cmd = [
        FFMPEG_PATH,
        "-loglevel",
        "warning",
        "-y",
        "-thread_queue_size",
        "4096",
        "-f",
        "h264",
        "-i",
        "-",
        "-c:v",
        "copy",
        "-f",
        "flv",
        "-rtmp_live",
        "live",
        youtube_url,
    ]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    threading.Thread(target=_drain_ffmpeg_output, args=(proc,), daemon=True).start()
    return proc


def _drain_ffmpeg_output(proc):
    if proc.stdout is not None:
        for line in proc.stdout:
            try:
                if isinstance(line, bytes):
                    line = line.decode(errors="replace")
                print(f"[FFmpeg] {line.rstrip()}")
            except Exception:
                pass
        proc.stdout.close()


def run_pipeline():
    stream_name, stream_key = resolve_stream_key()
    ffmpeg_proc = None
    picam2 = None
    output_handler = None

    try:
        print(f"[Birdcam] YouTube Live へのストリーミングを開始します。使用キー: {stream_name} ({_mask_stream_key(stream_key)})")
        ffmpeg_proc = create_ffmpeg_process(stream_key)
        output_handler = RingBufferH264Output(ffmpeg_proc)

        picam2 = Picamera2()
        config = picam2.create_video_configuration(
            main={"size": STREAM_RESOLUTION, "format": STREAM_FORMAT},
            lores={"size": LORES_RESOLUTION, "format": "YUV420"},
        )
        picam2.configure(config)
        picam2.start()

        picam2.start_recording(H264Encoder(bitrate=STREAM_BITRATE), FileOutput(output_handler))

        bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=25, detectShadows=False)
        print("[Birdcam] 配信と動体検知を開始しました。Ctrl+C で停止します。")

        last_motion_time = 0.0
        while True:
            if ffmpeg_proc.poll() is not None:
                raise RuntimeError("FFmpeg プロセスが終了しました。")
            if output_handler.stream_failed:
                raise RuntimeError("ストリーミング送信に失敗しました。")
            if time.time() - output_handler.last_stream_time > WATCHDOG_TIMEOUT_SECONDS:
                raise RuntimeError("ストリーム出力が停止しました。ウォッチドッグを発動します。")

            frame = picam2.capture_array("lores")
            x, y, w, h = ROI
            roi_frame = frame[y : y + h, x : x + w]
            if roi_frame.ndim == 3 and roi_frame.shape[2] == 3:
                gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
            else:
                # YUV420 の lores では単一チャネル（輝度）のみが返るため、そのまま使用します。
                gray = roi_frame
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            fg_mask = bg_subtractor.apply(gray)
            thresh = cv2.threshold(fg_mask, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            motion_detected = False
            for contour in contours:
                if cv2.contourArea(contour) >= MOTION_AREA_THRESHOLD:
                    motion_detected = True
                    break

            if motion_detected:
                now = time.time()
                if now - last_motion_time >= MOTION_COOLDOWN_SECONDS:
                    timestamp = int(now)
                    event_name = f"bird_event_{timestamp}"
                    output_handler.trigger_record(event_name=event_name)
                    print(f"[Motion] 動体検知: {event_name}")
                    last_motion_time = now

            time.sleep(MOTION_DETECTION_INTERVAL)

    except KeyboardInterrupt:
        print("[Birdcam] 停止要求を受け取りました。シャットダウンします。")
    except Exception as exc:
        print(f"[Error] パイプライン例外: {exc}")
        raise
    finally:
        if picam2 is not None:
            try:
                picam2.stop_recording()
            except Exception:
                pass
            try:
                picam2.stop()
            except Exception:
                pass
            try:
                picam2.close()
            except Exception:
                pass

        if output_handler is not None:
            try:
                output_handler.close()
            except Exception:
                pass

        if ffmpeg_proc is not None:
            try:
                if ffmpeg_proc.stdin:
                    ffmpeg_proc.stdin.close()
            except Exception:
                pass
            try:
                ffmpeg_proc.kill()
            except Exception:
                pass
            try:
                ffmpeg_proc.wait(timeout=5)
            except Exception:
                pass


def main():
    while True:
        try:
            print(f"[Birdcam] パイプライン開始: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            run_pipeline()
            print("[Birdcam] パイプラインが停止しました。5秒後に再起動します。")
            time.sleep(5)
        except KeyboardInterrupt:
            print("[Birdcam] 完全終了します。")
            break
        except Exception as exc:
            print(f"[Birdcam] 予期せぬエラー: {exc}")
            time.sleep(5)


if __name__ == "__main__":
    main()
