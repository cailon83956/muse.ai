"""Ghep: dat moi clip TTS dung vao khung SRT, roi tron voi am goc bang ffmpeg."""
import subprocess
from pathlib import Path

from pydub import AudioSegment

from .config import SETTINGS
from .srt import Segment
from .tts import fit_to_slot


def build_dub_track(segments: list[Segment], clips: list[Path], out_wav: Path) -> Path:
    total_ms = int(segments[-1].end * 1000) if segments else 0
    track = AudioSegment.silent(duration=total_ms)
    for s, clip_path in zip(segments, clips):
        clip = AudioSegment.from_file(clip_path)
        clip = fit_to_slot(clip, s.end - s.start)
        track = track.overlay(clip, position=int(s.start * 1000))
    track.export(out_wav, format="wav")
    return out_wav


def mux_video(video: Path, dub_wav: Path, out_mp4: Path) -> Path:
    """Am goc giam xuong 0.15 (-16dB gan dung), long tieng lam chinh.
    Dat original_volume=0 trong .env neu muon tat han tieng goc.
    """
    vol = SETTINGS.original_volume
    if vol <= 0:
        cmd = ["ffmpeg", "-y", "-i", str(video), "-i", str(dub_wav),
               "-map", "0:v", "-map", "1:a", "-c:v", "copy",
               "-c:a", "aac", "-shortest", str(out_mp4)]
    else:
        filt = f"[0:a]volume={vol}[a0];[1:a][a0]amix=inputs=2:duration=first[a]"
        cmd = ["ffmpeg", "-y", "-i", str(video), "-i", str(dub_wav),
               "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
               "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_mp4)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_mp4
