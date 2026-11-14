"""Ghep long tieng: fit TTS vao slot SRT -> timeline giong -> tron nhac nen -> mux video.
Khong them thu vien: atempo/pad bang ffmpeg, overlay timeline bang stdlib wave.
"""
import subprocess
import wave
from array import array
from pathlib import Path

from .srt import Segment


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def fit_wav(src: Path, target_s: float, out: Path) -> Path:
    """Can TTS vao dung slot: atempo 0.85-1.15x, thua/thieu thi pad/trim ve dung slot.
    Resample ve 16kHz mono luon."""
    dur = wav_duration(src)
    ratio = max(0.85, min(1.15, target_s / dur)) if dur > 0 else 1.0
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-af",
         f"atempo={ratio:.3f},aresample=16000,aformat=channel_layouts=mono,"
         f"apad,atrim=0:{target_s:.3f}",
         str(out)], check=True, capture_output=True, text=True)
    return out


def build_timeline(items: list[tuple[float, Path]], total_s: float, out: Path) -> Path:
    """Ghep cac wav segment vao dung vi tri start cua no, tren nen im."""
    sr = 16000
    buf = array("h", bytes(2 * int(total_s * sr)))
    for start, p in items:
        with wave.open(str(p), "rb") as w:
            n, raw = w.getnframes(), w.readframes(w.getnframes())
        data = array("h")
        data.frombytes(raw)
        off = int(start * sr)
        for i, v in enumerate(data):
            j = off + i
            if 0 <= j < len(buf):
                buf[j] = max(-32768, min(32767, buf[j] + v))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(buf.tobytes())
    return out


def mix_with_music(voice_wav: Path, music_wav: Path | None, out: Path) -> Path:
    if music_wav is None or not music_wav.exists():
        return voice_wav
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(voice_wav), "-i", str(music_wav),
         "-filter_complex",
         "[0:a]volume=1.0[v];[1:a]volume=0.25[m];[v][m]amix=inputs=2:duration=first",
         "-c:a", "pcm_s16le", str(out)],
        check=True, capture_output=True, text=True)
    return out


def mux_video(video: Path, audio_wav: Path, out_mp4: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-i", str(audio_wav),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
         "-shortest", str(out_mp4)],
        check=True, capture_output=True, text=True)
    return out_mp4


def build_dubbed_audio(vi_segments: list[Segment], tts_wavs: list[Path],
                       total_s: float, work_dir: Path,
                       music_wav: Path | None) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    fitted: list[tuple[float, Path]] = []
    for i, (s, wav) in enumerate(zip(vi_segments, tts_wavs)):
        target = max(0.3, s.end - s.start)
        f = work_dir / f"fit_{i:04d}.wav"
        fit_wav(wav, target, f)
        fitted.append((s.start, f))
    timeline = build_timeline(fitted, total_s, work_dir / "voice_timeline.wav")
    return mix_with_music(timeline, music_wav, work_dir / "dub_audio.wav")
