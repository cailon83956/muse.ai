"""ASR tren GPU, chi de xuat .srt.
- EN: faster-whisper large-v3, fp16 (CT2).
- VI: PhoWhisper-large (vinai) DA CONVERT sang CTranslate2, xem scripts/convert_phowhisper_ct2.sh.
  PhoWhisper goc la checkpoint PyTorch, faster-whisper KHONG load truc tiep duoc.
  Neu chua convert -> fallback large-v3 language='vi' (kem hon tieng Viet nhung chay duoc).
"""
import gc

from faster_whisper import WhisperModel

from .config import SETTINGS
from .srt import Segment, write_srt


def transcribe(wav_path: str, lang: str, srt_path: str) -> list[Segment]:
    if lang == "vi" and SETTINGS.phowhisper_ct2_dir:
        model_id, kwargs = SETTINGS.phowhisper_ct2_dir, {"language": "vi"}
    else:
        model_id, kwargs = SETTINGS.whisper_en, {"language": lang}
    # large-v3 fp16 ~6GB tren T4; dung vad_filter de bo doan im (bot hallucination)
    model = WhisperModel(model_id, device="cuda", compute_type="float16")
    try:
        segments, _info = model.transcribe(
            wav_path, beam_size=5, vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            word_timestamps=False, **kwargs,
        )
        out = [Segment(s.start, s.end, s.text) for s in segments if s.text.strip()]
    finally:
        del model
        gc.collect()  # CTranslate2 giai phong VRAM khi del model, khong can torch
    return out if write_srt(out, srt_path) else out
