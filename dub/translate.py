"""Dich EN <-> VI bang NLLB-200-distilled-600M CHAY TREN GPU (CUDA, fp16).
Khong dung deep-translator / Google nua — tat ca phai len GPU theo yeu cau.
Model ~600M params, fp16 ~1.2GB VRAM, load xong unload ngay sau khi dich.
"""
import gc

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from .config import SETTINGS
from .srt import Segment

LANG = {"en": "eng_Latn", "vi": "vie_Latn"}


def translate_segments(segments: list[Segment], src: str, tgt: str) -> list[Segment]:
    if src == tgt:
        return segments
    if src not in LANG or tgt not in LANG:
        raise ValueError(f"Chi ho tro en/vi, nhan {src}->{tgt}")
    tok = AutoTokenizer.from_pretrained(SETTINGS.nllb_model)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        SETTINGS.nllb_model, torch_dtype=torch.float16).to("cuda").eval()
    try:
        out_texts: list[str] = []
        for i in range(0, len(segments), 8):  # batch 8 cau/lan
            batch = [s.text.strip() for s in segments[i:i + 8]]
            inputs = tok(batch, return_tensors="pt", padding=True,
                         truncation=True, max_length=128).to("cuda")
            with torch.no_grad():
                gen = model.generate(**inputs, forced_bos_token_id=tok.lang_code_to_id[LANG[tgt]],
                                     max_length=128, num_beams=4)
            out_texts.extend(tok.batch_decode(gen, skip_special_tokens=True))
        return [Segment(s.start, s.end, t or s.text)
                for s, t in zip(segments, out_texts)]
    finally:
        del model, tok
        gc.collect()
        torch.cuda.empty_cache()
