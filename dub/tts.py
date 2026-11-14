"""TTS — TAT CA TREN GPU.
- VI + EN: deu dung VieNeu-TTS v3 Turbo, package `vieneu[cuda]==3.7.1`.
  VieNeu la song ngu EN-VI nen tieng Anh cung dung no, khong dung edge-tts
  (cloud) nua. Khong con fallback KorvaTTS (ONNX/CPU).
- API: Vieneu(precision='fp16'), .infer_batch(texts, voice=..., batch_size=8).
  Tren CUDA no tu bat PyTorch + batching.
"""
import asyncio
import gc
from pathlib import Path

import torch
from pydub import AudioSegment

from .config import SETTINGS
from .srt import Segment


def _vieneu():
    from vieneu import Vieneu  # import cham: tranh keo torch khi chi chay /sub

    return Vieneu(precision=SETTINGS.vieneu_precision)


def synth_vieneu(segments: list[Segment], out_dir: Path) -> list[Path]:
    """Batch 8 cau/lan tren GPU, tra ve 1 file wav 48kHz cho moi segment."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tts = _vieneu()
    try:
        texts = [s.text for s in segments]
        audios = tts.infer_batch(texts, voice=SETTINGS.vieneu_voice,
                                 batch_size=SETTINGS.vieneu_batch_size)
        paths = []
        for i, audio in enumerate(audios):
            p = out_dir / f"{i:04d}.wav"
            if hasattr(audio, "export"):
                audio.export(p, format="wav")
            else:
                import soundfile as sf
                sf.write(p, audio, 48000)
            paths.append(p)
        return paths
    finally:
        del tts
        gc.collect()
        torch.cuda.empty_cache()


async def synth(segments: list[Segment], lang: str, out_dir: Path) -> list[Path]:
    # lang chi de giu chu ky ham cu, ca vi va en deu qua VieNeu GPU
    return await asyncio.to_thread(synth_vieneu, segments, out_dir)


def fit_to_slot(clip: AudioSegment, slot_s: float) -> AudioSegment:
    """Can toc do TTS ve vua khung SRT: rate = dur/slot, kep 0.85-1.15x.
    Neu van dai hon slot sau khi tang toc toi da -> cat bot. Neu ngan hon -> dem silence.
    (pydub/ffmpeg la xu ly audio thuan CPU, khong co ban GPU — phan nay nhe, khong dang ke.)
    """
    dur = len(clip) / 1000
    rate = max(0.85, min(1.15, dur / slot_s)) if slot_s > 0 else 1.0
    if rate != 1.0:
        clip = clip.speedup(playback_speed=rate)
    target_ms = int(slot_s * 1000)
    if len(clip) > target_ms:
        return clip[:target_ms]
    return clip + AudioSegment.silent(duration=target_ms - len(clip))
