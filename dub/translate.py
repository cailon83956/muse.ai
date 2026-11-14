"""Dich EN -> VI bang NLLB-200-distilled-600M tren GPU, fp16, batch 8.
Chi chay khi nguon la tieng Anh. Nguon tieng Viet thi khong dich — vi.srt
chinh la orig.srt.
"""
import gc

from .config import SETTINGS
from .srt import Segment


def translate_segments(segments: list[Segment]) -> list[Segment]:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    model_id = SETTINGS.nllb_model
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_id, torch_dtype=torch.float16).to("cuda").eval()
    try:
        out: list[Segment] = []
        for i in range(0, len(segments), 8):
            batch = segments[i:i + 8]
            enc = tok([s.text for s in batch], return_tensors="pt",
                      padding=True, truncation=True, max_length=256).to("cuda")
            with torch.no_grad():
                gen = model.generate(
                    **enc, forced_bos_token_id=tok.convert_tokens_to_ids("vie_Latn"),
                    max_new_tokens=256)
            for s, g in zip(batch, gen):
                out.append(Segment(s.start, s.end,
                                   tok.decode(g, skip_special_tokens=True).strip()))
        return out
    finally:
        del model
        gc.collect()
        torch.cuda.empty_cache()
