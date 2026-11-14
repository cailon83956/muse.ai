"""SRT: 1 dinh dang duy nhat cho ca ASR -> dich -> TTS -> ghep."""
from dataclasses import dataclass


@dataclass
class Segment:
    start: float  # giay
    end: float
    text: str


def fmt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments: list[Segment], path: str) -> str:
    lines = []
    for i, s in enumerate(segments, 1):
        lines.append(f"{i}\n{fmt_ts(s.start)} --> {fmt_ts(s.end)}\n{s.text.strip()}\n")
    Path = __import__("pathlib").Path(path)
    Path.write_text("\n".join(lines), encoding="utf-8")
    return path


def parse_ts(ts: str) -> float:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def read_srt(path: str) -> list[Segment]:
    out, block = [], []
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip():
            if len(block) >= 3:
                a, b = block[1].split(" --> ")
                out.append(Segment(parse_ts(a), parse_ts(b), " ".join(block[2:])))
            block = []
        else:
            block.append(line)
    if len(block) >= 3:
        a, b = block[1].split(" --> ")
        out.append(Segment(parse_ts(a), parse_ts(b), " ".join(block[2:])))
    return out
