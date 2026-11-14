"""Tai video bang yt-dlp (subprocess, khong dung lib de tranh ket version).
YouTube cong khai: khong can cookie. Facebook rieng tu: can cookies/cookies.txt.
403 thuong do yt-dlp cu hoac YouTube chan client mac dinh -> update + player_client=android.
"""
import os
import subprocess
import sys
from pathlib import Path

from .config import SETTINGS

# yt-dlp cai trong cung venv voi python dang chay; khi chay qua systemd
# ExecStart=.venv/bin/python, PATH co the khong chua .venv/bin -> resolve tuong doi.
_YTDLP = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
if not os.path.exists(_YTDLP):
    _YTDLP = "yt-dlp"

MAX_1080 = "bv*[height<=1080]+ba/b[height<=1080]/b"


def download(url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tpl = str(out_dir / "%(id)s.%(ext)s")
    cmd = [
        _YTDLP, "--no-playlist", "--merge-output-format", "mp4",
        "-f", MAX_1080, "-o", tpl,
        # Giam 403 tren YouTube: dung android client thay vi web client mac dinh
        "--extractor-args", "youtube:player_client=android",
        "--print", "after_move:filepath", url,
    ]
    if SETTINGS.cookies_file.exists():
        cmd[1:1] = ["--cookies", str(SETTINGS.cookies_file)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        err = (r.stderr or r.stdout)[-2000:]
        hint = ""
        if ("403" in err or "Forbidden" in err or "Sign in to confirm" in err
                or "login" in err.lower()) and not SETTINGS.cookies_file.exists():
            hint = " — Bi chan / can dang nhap: upload cookies.txt bang lenh /cookies tren Discord roi /sub lai."
        raise RuntimeError(f"yt-dlp loi ({r.returncode}): {err}{hint}")
    # --print after_move in ra duong dan file cuoi cung
    path = Path(r.stdout.strip().splitlines()[-1])
    if not path.exists():
        raise RuntimeError(f"yt-dlp xong nhung khong thay file: {r.stdout[-500:]}")
    return path


def extract_audio(video: Path, out_wav: Path) -> Path:
    """Tach audio 16kHz mono cho Whisper (nhanh + nhe VRAM hon 48k stereo)."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(out_wav)],
        check=True, capture_output=True, text=True,
    )
    return out_wav
