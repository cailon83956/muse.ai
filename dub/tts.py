"""TTS.
- VI: VieNeu-TTS v3 Turbo, package `vieneu`, API that: Vieneu(precision='fp16'),
  .infer(text, voice=...) / .infer_batch(texts, voice=..., batch_size=8).
  Tren CUDA no tu bat PyTorch + batching; tren CPU tu chuyen ONNX.
  Khong co tham so max_streams=8 trong SDK nay - dung infer_batch(batch_size=8).
  License CC BY-NC 4.0 (ban 0.3B) - kiem tra lai truoc khi dung thuong mai.
- EN: edge-tts (cloud Microsoft, mien phi, khong ton VRAM).
- Fallback VI nhe: KorvaTTS (ONNX, 44.1kHz, pip `korvatts`, Apache-2.0) khi
  VieNeu loi / may khong co torch. Chi dung khi can, khong cai mac dinh.
"""
import asyncio
from pathlib import Path

from pydub import AudioSegment

from .config import SETTINGS
from .srt import Segment


def _vieneu():
    from vieneu import Vieneu  # import cham: tranh keo torch khi chi chay /sub hoac edge-tts

    return Vieneu(precision=SETTINGS.vieneu_precision)


def synth_vi(segments: list[Segment], out_dir: Path) -> list[Path]:
    """Batch 8 cau/lan tren GPU, tra ve 1 file wav 48kHz cho moi segment."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tts = _vieneu()
    try:
        texts = [s.text for s in segments]
        audios = tts.infer_batch(texts, voice=SETTINGS.vieneu_voice,
                                 batch_size=SETTINGS.vieneu_batch_size)
        paths = []
        for i, audio in enumerate(audios):
            # infer_batch tra ve numpy array (48kHz) hoac AudioSegment tuy version SDK
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
        import gc, torch
        gc.collect()
        torch.cuda.empty_cache()


async def synth_en(segments: list[Segment], out_dir: Path) -> list[Path]:
    import edge_tts  # import cham: chi can khi dich sang tieng Anh

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, s in enumerate(segments):
        p = out_dir / f"{i:04d}.mp3"
        await edge_tts.Communicate(s.text, SETTINGS.edge_voice_en).save(str(p))
        paths.append(p)
    return paths


async def synth(segments: list[Segment], lang: str, out_dir: Path) -> list[Path]:
    if lang == "vi":
        return await asyncio.to_thread(synth_vi, segments, out_dir)
    return await synth_en(segments, out_dir)


def fit_to_slot(clip: AudioSegment, slot_s: float) -> AudioSegment:
    """Can toc do TTS ve vua khung SRT: rate = dur/slot, kep 0.85-1.15x.
    Neu van dai hon slot sau khi tang toc toi da -> cat bot (shortcut: cat, khi nao
    can dich ngan hon thi sua o buoc dich, khong sua o day). Neu ngan hon -> dem silence.
    """
    dur = len(clip) / 1000
    rate = max(0.85, min(1.15, dur / slot_s)) if slot_s > 0 else 1.0
    if rate != 1.0:
        clip = clip.speedup(playback_speed=rate)
    target_ms = int(slot_s * 1000)
    if len(clip) > target_ms:
        return clip[:target_ms]
    return clip + AudioSegment.silent(duration=target_ms - len(clip))
