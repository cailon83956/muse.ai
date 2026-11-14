"""Demucs: tach giong (vocals) khoi nhac nen cua audio goc.
Chay bang subprocess `python -m demucs` (cung venv) de VRAM giai phong
hoan toan khi xong — khong giu model torch trong tien trinh bot.
Model htdemucs, --two-stems=vocals -> vocals.wav + no_vocals.wav (nhac).
Loi / khong cai demucs -> tra ve None, pipeline fallback dung audio goc.
"""
import subprocess
import sys
from pathlib import Path

from .config import SETTINGS


def separate(audio_wav: Path, out_dir: Path) -> tuple[Path, Path] | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [sys.executable, "-m", "demucs", "-n", SETTINGS.demucs_model,
         "--two-stems=vocals", "-o", str(out_dir), str(audio_wav)],
        capture_output=True, text=True, timeout=3600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"Demucs loi: {(r.stderr or r.stdout)[-1000:]}")
    # demucs xuat: <out_dir>/<model>/<ten file>/vocals.wav + no_vocals.wav
    base = out_dir / SETTINGS.demucs_model / audio_wav.stem
    vocals, music = base / "vocals.wav", base / "no_vocals.wav"
    if not vocals.exists():
        raise RuntimeError(f"Demucs xong nhung khong thay vocals.wav o {base}")
    return vocals, music
