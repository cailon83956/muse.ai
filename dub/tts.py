"""TTS tieng Viet bang VieNeu v3 Turbo tren GPU.
SDK: pip install "vieneu[cuda]" — khong co extra 'gpu' (do la v1/v2 cu).
API theo docs v3: Vieneu(precision=...), infer_batch(batch_size=8).
Tra ve 1 file wav moi segment (16kHz mono), de mux.py can thoi gian.
"""
import gc
from pathlib import Path

from .config import SETTINGS
from .srt import Segment


def synth_segments(segments: list[Segment], out_dir: Path) -> list[Path]:
    from vieneu import Vieneu

    out_dir.mkdir(parents=True, exist_ok=True)
    tts = Vieneu(precision="float16")
    try:
        texts = [s.text for s in segments]
        kwargs = {"batch_size": 8}
        if getattr(SETTINGS, "vieneu_voice", ""):
            kwargs["voice"] = SETTINGS.vieneu_voice
        # infer_batch tra ve list wav (numpy / path tuy ban) — chuan hoa ve file
        results = tts.infer_batch(texts, **kwargs)
        paths: list[Path] = []
        for i, r in enumerate(results):
            p = out_dir / f"seg_{i:04d}.wav"
            if isinstance(r, (str, Path)) and Path(r).exists():
                Path(r).rename(p)
            else:
                # numpy array 48kHz: ghi wav bang stdlib (khong them soundfile)
                import numpy as np
                import wave
                arr = np.asarray(r)
                if arr.dtype != np.int16:
                    arr = (arr * 32767).clip(-32768, 32767).astype(np.int16)
                with wave.open(str(p), "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(48000)
                    w.writeframes(arr.tobytes())
            paths.append(p)
        return paths
    finally:
        del tts
        gc.collect()
