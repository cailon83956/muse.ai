"""Pipeline tuan tu: 1 job chay tai 1 thoi diem (T4 khong chiu noi 2 job).
Thu tu: download -> audio 16k -> ASR -> (dich neu can) -> TTS -> fit SRT -> mux.
Model duoc load/unload trong tung buoc, khong giu 2 model cung luc.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import asr, mux, tts
from .config import SETTINGS, require_gpu
from .downloader import download, extract_audio
from .srt import Segment, write_srt
from .translate import translate_segments


@dataclass
class Job:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    url: str = ""
    mode: str = "dub"  # dub | sub
    src_lang: str = "en"
    tgt_lang: str = "vi"
    status: str = "queued"
    progress: str = ""
    video: Path | None = None
    srt: Path | None = None
    out_mp4: Path | None = None
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
        segs = await asyncio.to_thread(asr.transcribe, str(wav), job.src_lang, str(d / "orig.srt"))
        if not segs:
            raise RuntimeError("ASR tra ve 0 segment - video khong co loi noi?")
        job.srt = d / "orig.srt"
        if job.mode == "sub":
            job.status, job.progress = "done", f"Xong: {len(segs)} cau"
            return job
        job.status, job.progress = "translating", "Dang dich..."
        dub_segs = await asyncio.to_thread(translate_segments, segs, job.src_lang, job.tgt_lang)
        write_srt(dub_segs, str(d / "dub.srt"))
        job.status, job.progress = "tts", "Dang tong hop giong noi..."
        clips = await tts.synth(dub_segs, job.tgt_lang, d / "tts")
        job.status, job.progress = "muxing", "Dang ghep video..."
        track = mux.build_dub_track(dub_segs, clips, d / "dub.wav")
        job.out_mp4 = mux.mux_video(job.video, track, d / "dubbed.mp4")
        job.srt = d / "dub.srt"
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
