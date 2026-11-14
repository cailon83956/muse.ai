"""Fix lech mieng cho .srt — nhe, KHONG them thu vien nao.
Chi dung stdlib (wave + math). Khong Demucs, khong WhisperX, khong Wav2Lip.

Van de: Whisper segment start/end thuong dem them khoang im dau/cuoi, va
word start cua Whisper som hon mieng that ~150ms (FA-Bench). Nen phu de
hien som / tat muon so voi mieng.

Cach fix, 2 lop:
1. ASR (asr.py): word_timestamps=True, lay start/end tu tu dau/cuoi thay vi
   ca segment — chat hon nhieu.
2. O day: snap bang nang luong am thanh that. Doc wav 16kHz, tinh RMS moi
   10ms, tim khung noi dau tien / cuoi cung trong cua so ±0.3s quanh moc
   Whisper. Nguong = 25% RMS dinh cua chinh doan do (tu thich nghi, khong
   dung nguong cung).
3. Tru 80ms lead-in o dau (phu de hien truoc mieng mo 1 chut la chuan),
   cong 50ms tail o cuoi, roi kep de khong chong len cau ke tiep.
"""
import math
import wave
from array import array

from .srt import Segment

FRAME_MS = 10
SEARCH_S = 0.3
LEAD_S = 0.08
TAIL_S = 0.05
MIN_DUR_S = 0.3


def _frame_rms(samples: array, sr: int) -> list[float]:
    per = max(1, sr * FRAME_MS // 1000)
    out = []
    for i in range(0, len(samples) - per + 1, per):
        chunk = samples[i:i + per]
        out.append(math.sqrt(sum(x * x for x in chunk) / len(chunk)))
    return out


def _first_speech(rms: list[float], lo: int, hi: int, thr: float) -> int | None:
    # Can 2 khung lien tiep vuot nguong de tranh spike don; hi bao gom ca
    for i in range(max(0, lo), min(len(rms) - 1, hi + 1)):
        if rms[i] > thr and rms[i + 1] > thr:
            return i
    return None


def _last_speech(rms: list[float], lo: int, hi: int, thr: float) -> int | None:
    # Khung cuoi: khung ke truoc cung phai noi (khung ke sau la im, khong dung duoc)
    for i in range(min(len(rms) - 1, hi), max(0, lo) - 1, -1):
        if rms[i] > thr and (i == 0 or rms[i - 1] > thr):
            return i
    return None


def align_segments(segments: list[Segment], wav_path: str) -> list[Segment]:
    if not segments:
        return segments
    with wave.open(wav_path, "rb") as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        raw = w.readframes(n)
    samples = array("h")
    samples.frombytes(raw)
    if ch == 2:  # phong truong hop wav stereo lot vao
        samples = array("h", samples[::2])
    rms = _frame_rms(samples, sr)
    frame_s = FRAME_MS / 1000
    out: list[Segment] = []
    for idx, s in enumerate(segments):
        # Cua so tim kiem khong duoc lan sang cau ke truoc/sau — neu khong se
        # snap nham vao duoi cau truoc / dau cau sau khi 2 cau gan nhau.
        prev_end = segments[idx - 1].end if idx > 0 else 0.0
        next_start = segments[idx + 1].start if idx + 1 < len(segments) else None
        lo_i = int(max(prev_end, s.start - SEARCH_S) / frame_s) - 1
        hi_i = int((s.start + SEARCH_S) / frame_s) + 1
        a = int(s.start / frame_s)
        b = int(s.end / frame_s)
        peak = max(rms[a:b + 1]) if b >= a and rms else 0
        if peak <= 0:
            out.append(s)
            continue
        thr = peak * 0.25
        first = _first_speech(rms, lo_i, hi_i, thr)
        new_start = (first * frame_s - LEAD_S) if first is not None else s.start
        lo2 = int(max(0, s.end - SEARCH_S) / frame_s) - 1
        hi2 = int(min(next_start if next_start is not None else s.end + SEARCH_S,
                      s.end + SEARCH_S) / frame_s) + 1
        last = _last_speech(rms, lo2, hi2, thr)
        new_end = ((last + 1) * frame_s + TAIL_S) if last is not None else s.end
        new_start = max(0.0, new_start)
        if new_end - new_start < MIN_DUR_S:
            new_end = new_start + MIN_DUR_S
        out.append(Segment(new_start, new_end, s.text))
    # Kep chong lap: cau truoc khong duoc lan sang cau sau
    for i in range(len(out) - 1):
        if out[i].end > out[i + 1].start - 0.04:
            out[i] = Segment(out[i].start, max(out[i].start + MIN_DUR_S,
                                                out[i + 1].start - 0.04), out[i].text)
    return out
