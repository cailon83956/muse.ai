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


def media_duration(path: Path) -> float:
    """Do dai file media (giay) bang ffprobe — dung de timeline giong bang dung do dai video."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True)
    return float(r.stdout.strip())


def trim_silence(src: Path, out: Path) -> Path:
    """Cat im o dau/cuoi cau TTS de loi bat dau dung luc mieng mo (TTS hay co 100-300ms im dau)."""
    thr = "-45dB"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-af",
         f"silenceremove=start_periods=1:start_threshold={thr}:start_silence=0.03,"
         f"areverse,"
         f"silenceremove=start_periods=1:start_threshold={thr}:start_silence=0.05,"
         f"areverse",
         str(out)], check=True, capture_output=True, text=True)
    if not out.exists() or wav_duration(out) < 0.05:  # toan im -> giu ban goc
        return src
    return out


MIN_TEMPO = 0.85   # cham toi da khi TTS ngan hon slot
NATURAL_MAX = 1.25  # tang toc "de chiu" truoc khi muon lan sang khoang lang
OVERFLOW_MAX_S = 0.4  # toi da cho loi tran qua cuoi slot (mieng da dong, giong con chay)
HARD_MAX_TEMPO = 2.0  # tran cuoi cung, tranh bi cat cut


def fit_wav(src: Path, slot_s: float, limit_s: float, out: Path) -> Path:
    """Can TTS vao slot SRT.

    atempo la he so TANG TOC (atempo=2 -> ngan di 2 lan), nen tempo = dur / slot.
    - TTS ngan hon slot: cham lai toi MIN_TEMPO cho vua mieng, phan thua de im.
    - TTS dai hon slot: tang toc toi NATURAL_MAX; neu van dai thi muon tiep khoang
      lang truoc cau ke (toi da OVERFLOW_MAX_S qua cuoi slot) thay vi tang toc manh;
      het cho moi tang toc them (toi HARD_MAX_TEMPO). Khong bao gio cat vao giua loi noi
      tru truong hop cuc doan.
    Resample ve 16kHz mono.
    """
    trimmed = trim_silence(src, out.with_suffix(".trim.wav"))
    dur = wav_duration(trimmed)
    limit_s = max(slot_s, min(limit_s, slot_s + OVERFLOW_MAX_S))
    if dur <= 0:
        tempo, target = 1.0, slot_s
    elif dur <= slot_s:
        tempo, target = max(MIN_TEMPO, dur / slot_s), slot_s
    else:
        target = min(limit_s, max(slot_s, dur / NATURAL_MAX))
        tempo = min(HARD_MAX_TEMPO, max(1.0, dur / target))
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(trimmed), "-af",
         f"atempo={tempo:.4f},aresample=16000,aformat=channel_layouts=mono,"
         f"atrim=0:{limit_s:.3f}",
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
                       music_wav: Path | None, start_shift: float = 0.0) -> Path:
    """start_shift: cong them vao moc start khi dat giong (giay). Phu de co lead-in
    truoc mieng (align.LEAD_S) nhung giong long tieng thi phai vao dung luc mieng mo
    (am thanh som hon hinh >~45ms la nguoi xem thay lech)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    fitted: list[tuple[float, Path]] = []
    n = len(vi_segments)
    for i, (s, wav) in enumerate(zip(vi_segments, tts_wavs)):
        start = min(s.start + start_shift, max(0.0, s.end - 0.3))
        slot = max(0.3, s.end - start)
        nxt = vi_segments[i + 1].start if i + 1 < n else total_s
        limit = max(slot, nxt - start - 0.06)  # khong de len dau cau ke
        f = work_dir / f"fit_{i:04d}.wav"
        fit_wav(wav, slot, limit, f)
        fitted.append((start, f))
    timeline = build_timeline(fitted, total_s, work_dir / "voice_timeline.wav")
    return mix_with_music(timeline, music_wav, work_dir / "dub_audio.wav")
