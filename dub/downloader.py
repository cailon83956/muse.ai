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


def _run_ytdlp(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"[downloader] running: {' '.join(cmd[:8])} ...", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    print(f"[downloader] finished rc={r.returncode}", flush=True)
    return r


def download(url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tpl = str(out_dir / "%(id)s.%(ext)s")
    base = [
        "--no-playlist", "--merge-output-format", "mp4",
        "-f", MAX_1080, "-o", tpl,
        "--remote-components", "ejs:github",
        "--print", "after_move:filepath", url,
    ]

    # Thu tu thu:
    # 1) Neu co cookies: thu voi cookies (client mac dinh, ho tro cookies) —
    #    phuc vu video rieng tu / gioi han tuoi.
    # 2) Neu that bai hoac khong co cookies: thu android client KHONG cookies —
    #    android bo qua chan bot theo IP (nhung khong ho tro cookies).
    attempts: list[list[str]] = []
    if SETTINGS.cookies_file.exists():
        attempts.append([_YTDLP, "--cookies", str(SETTINGS.cookies_file)] + base)
    attempts.append([_YTDLP, "--extractor-args", "youtube:player_client=android"] + base)

    last_err = ""
    for cmd in attempts:
        r = _run_ytdlp(cmd)
        if r.returncode == 0:
            lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
            if lines:
                path = Path(lines[-1])
                if path.exists():
                    return path
            last_err = f"yt-dlp xong nhung khong thay file: {r.stdout[-500:]}"
            continue
        last_err = (r.stderr or r.stdout)[-2000:]
        # Neu loi format/khong ho tro cookies, thu attempt tiep theo
        if ("Requested format is not available" in last_err
                or "Skipping client" in last_err
                or "Sign in to confirm" in last_err
                or "403" in last_err or "Forbidden" in last_err):
            continue
        # Loi khac (vd: URL sai) -> dung luon
        break

    hint = ""
    if ("403" in last_err or "Forbidden" in last_err or "Sign in to confirm" in last_err
            or "login" in last_err.lower()) and not SETTINGS.cookies_file.exists():
        hint = " — Bi chan / can dang nhap: upload cookies.txt bang lenh /cookies tren Discord roi /sub lai."
    raise RuntimeError(f"yt-dlp loi: {last_err}{hint}")


def extract_audio(video: Path, out_wav: Path) -> Path:
    """Tach audio 16kHz mono cho Whisper (nhanh + nhe VRAM hon 48k stereo)."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(out_wav)],
        check=True, capture_output=True, text=True,
    )
    return out_wav