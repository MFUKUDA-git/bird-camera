#!/usr/bin/env python3
"""YouTube Live テスト用の最小送信スクリプト。

 /etc/birdcam/birdcam.env を読み込み、YOUTUBE_STREAM_KEY を使って
 FFmpeg でテスト映像を YouTube Live に送信する。

 使い方:
   python3 youtube_live_test.py

 注意:
   - 送信先は /etc/birdcam/birdcam.env の YOUTUBE_STREAM_KEY を利用する
   - キーはログに完全表示しない（マスク表示）
   - テスト用なので、本番の録画・検知コードは含めない
"""

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ENV_PATH = Path("/etc/birdcam/birdcam.env")
FFMPEG_PATH = "/usr/bin/ffmpeg"
YOUTUBE_URL_TEMPLATE = "rtmp://a.rtmp.youtube.com/live2/{key}"


def mask_key(key: str) -> str:
    if not key:
        return "<empty>"
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


def parse_env_file(path: Path):
    """/etc/birdcam/birdcam.env を shell 風に読み込む。"""
    values = {}
    if not path.exists():
        raise FileNotFoundError(f"環境ファイルが見つかりません: {path}")

    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("export "):
                line = line[len("export ") :].strip()

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
                value = value[1:-1]

            values[key] = value

    return values


def load_stream_key():
    """環境変数または /etc/birdcam/birdcam.env からストリームキーを取得する。"""
    env_values = parse_env_file(ENV_PATH)
    key = os.environ.get("YOUTUBE_STREAM_KEY") or env_values.get("YOUTUBE_STREAM_KEY", "")
    if not key:
        raise ValueError(
            "YOUTUBE_STREAM_KEY が見つかりません。"
            f"{ENV_PATH} に設定してください。"
        )
    return key.strip()


def build_ffmpeg_command(stream_key: str):
    url = YOUTUBE_URL_TEMPLATE.format(key=stream_key)
    cmd = [
        FFMPEG_PATH,
        "-loglevel",
        "warning",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30",
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-b:v",
        "2000k",
        "-maxrate",
        "2000k",
        "-bufsize",
        "4000k",
        "-g",
        "30",
        "-f",
        "flv",
        url,
    ]
    return cmd


def main():
    try:
        stream_key = load_stream_key()
        print(f"[TestStream] Using stream key: {mask_key(stream_key)}")
        print(f"[TestStream] Loading env: {ENV_PATH}")
        cmd = build_ffmpeg_command(stream_key)
        print("[TestStream] Start FFmpeg stream to YouTube Live")
        print("[TestStream] Ctrl+C to stop")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        if proc.stdout is None:
            raise RuntimeError("FFmpeg の標準出力を取得できませんでした")

        for line in proc.stdout:
            if line:
                print(line.rstrip())

        return proc.wait()

    except KeyboardInterrupt:
        print("\n[TestStream] 停止要求を受け取りました")
        return 0
    except Exception as exc:
        print(f"[TestStream] Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
