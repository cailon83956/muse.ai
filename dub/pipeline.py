"""Pipeline chi lam phu de: download -> audio 16k -> ASR -> .srt. Het.
Khong dich, khong TTS, khong ghep video.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import align, asr
from .config import SETTINGS, require_gpu
from .downloader import download, extract_audio
from .srt import write_srt


@dataclass
class Job:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    url: str = ""
    src_lang: str = "en"
    status: str = "queued"
    progress: str = ""
    video: Path | None = None
    srt: Path | None = None
    error: str = ""


async def run_job(job: Job) -> Job:
    d = SETTINGS.jobs_dir / job.id
    d.mkdir(parents=True, exist_ok=True)
    try:
        await asyncio.to_thread(require_gpu)  # fail nhanh neu mat GPU
        job.status, job.progress = "downloading", "Dang tai video..."
        job.video = await asyncio.to_thread(download, job.url, d)
        job.status, job.progress = "asr", "Dang nhan dang giong noi..."
        wav = await asyncio.to_thread(extract_audio, job.video, d / "audio16k.wav")
        segs = await asyncio.to_thread(asr.transcribe, str(wav), job.src_lang)
        if not segs:
            raise RuntimeError("ASR tra ve 0 segment - video khong co loi noi?")
        job.status, job.progress = "aligning", "Dang can moc phu de khop mieng..."
        segs = await asyncio.to_thread(align.align_segments, segs, str(wav))
        write_srt(segs, str(d / "orig.srt"))
        job.srt = d / "orig.srt"
        job.status, job.progress = "done", f"Xong: {len(segs)} cau"
        return job
    except Exception as e:
        job.status, job.error = "failed", str(e)[:1000]
        return job


class Worker:
    """asyncio.Queue + 1 worker. Bot chi enqueue, khong chay job truc tiep."""

    def __init__(self):
        self.q: asyncio.Queue[Job] = asyncio.Queue()
        self.current: Job | None = None

    async def start(self):
        while True:
            job = await self.q.get()
            self.current = job
            await run_job(job)
            self.current = None
            self.q.task_done()
