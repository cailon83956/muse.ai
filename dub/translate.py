"""Dich EN -> VI theo tung segment SRT (giu nguyen moc thoi gian).
Dung deep-translator (Google, khong can API key). Gioi han: rate-limit neu dich
hang loat, video dai thi nen doi sang NLLB local (facebook/nllb-200-distilled-600M).
"""
from deep_translator import GoogleTranslator

from .srt import Segment


def translate_segments(segments: list[Segment], src: str, tgt: str) -> list[Segment]:
    if src == tgt:
        return segments
    tr = GoogleTranslator(source=src, target=tgt)
    out = []
    for s in segments:
        # Dich tung cau ngan: tranh dich ca doan dai bi cat / lech nghia
        text = tr.translate(s.text.strip()) or s.text
        out.append(Segment(s.start, s.end, text))
    return out
