"""Pipeline bot:
  /sub      : download -> Demucs tach giong -> ASR (vocals) -> align khop mieng
              -> dich EN->VI (neu EN) -> xuat orig.srt + vi.srt (rieng biet)
  /dub      : nhu /sub + VieNeu TTS tieng Viet -> fit slot -> tron nhac nen
              -> mux video goc -> dubbed.mp4 + orig.srt + vi.srt
  /separate : download -> Demucs -> vocals.mp3 + music.mp3
Demucs that bai -> fallback audio goc (ghi warning, khong fail job).
"""
import asyncio
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import align, asr, demucs, mux, translate, tts
from .config import SETTINGS, require_gpu
from .downloader import download, extract_audio
from .srt import Segment, read_srt, write_srt

# (stage, pct) — bot dung pct de ve thanh tien trinh
STAGES = {
    "downloading": ("📥 Dang tai video...", 10),
    "separating": ("🎚️ Demucs: dang tach giong / nhac...", 30),
    "asr": ("🎙️ Dang nhan dang giong noi...", 50),
    "aligning": ("👄 Dang can moc phu de khop mieng...", 60),
    "translating": ("🌐 Dang dich sang tieng Viet...", 68),
    "tts": ("🗣️ VieNeu: dang doc tieng Viet...", 82),
    "muxing": ("🎬 Dang ghep video long tieng...", 94),
    "done": ("✅ Xong", 100),
}


@dataclass
class Job:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    url: str = ""
    src_lang: str = "en"
    mode: str = "sub"  # sub | dub | separate
    voice: str = ""  # VieNeu voice (de trong = mac dinh)
    status: str = "queued"
    progress: str = ""
    pct: int = 0
    video: Path | None = None
    uploaded: bool = False  # True = video da upload qua Discord, bo qua yt-dlp
    subs_file: Path | None = None  # file .srt da dich do user upload (chi /dub)
    demucs_enabled: bool = True  # False = tat Demucs, dung audio goc luon
    srt: Path | None = None       # orig.srt
    vi_srt: Path | None = None    # vi.srt (da dich, hoac = orig neu nguon VI)
    dubbed: Path | None = None    # dubbed.mp4
    vocals: Path | None = None    # vocals.mp3 (separate)
    music: Path | None = None     # music.mp3 (separate)
    warning: str = ""
    error: str = ""

    def set_stage(self, key: str):
        self.status = key
        self.progress, self.pct = STAGES[key]


def _to_mp3(wav: Path, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-y", "-i", str(wav), "-c:a", "libmp3lame",
                    "-b:a", "192k", str(out)],
                   check=True, capture_output=True, text=True)
    return out


def _extract_full_audio(video: Path, out_wav: Path) -> Path:
    """Audio goc 44.1kHz stereo cho Demucs (khong dung ban 16k mono)."""
    subprocess.run(["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "2",
                    "-ar", "44100", "-c:a", "pcm_s16le", str(out_wav)],
                   check=True, capture_output=True, text=True)
    return out_wav


def _asr_with_demucs(job: Job, d: Path) -> tuple[list[Segment], Path | None, Path | None]:
    """Tai audio -> Demucs (neu bat) -> ASR tren vocals. Tra (segments, vocals_wav, music_wav)."""
    full = _extract_full_audio(job.video, d / "audio_full.wav")
    vocals_wav, music_wav = None, None
    if job.demucs_enabled:
        job.set_stage("separating")
        try:
            vocals_wav, music_wav = demucs.separate(full, d / "demucs")
        except Exception as e:
            job.warning += f"Demucs that bai, dung audio goc: {str(e)[:200]}. "
    else:
        job.warning += "Demucs tat theo yeu cau, dung audio goc. "
    src_wav = vocals_wav if vocals_wav else full
    job.set_stage("asr")
    wav16 = extract_audio(src_wav, d / "audio16k.wav")
    segs = asr.transcribe(str(wav16), job.src_lang)
    if not segs:
        raise RuntimeError("ASR tra ve 0 segment - video khong co loi noi?")
    job.set_stage("aligning")
    segs = align.align_segments(segs, str(wav16))
    return segs, vocals_wav, music_wav


def _translate_if_en(job: Job, segs: list[Segment], d: Path) -> tuple[list[Segment], Path]:
    """Viet: vi.srt = orig.srt. Anh: dich -> vi.srt rieng."""
    orig = write_srt(segs, str(d / "orig.srt"))
    if job.src_lang == "vi":
        vi = write_srt(segs, str(d / "vi.srt"))
        return segs, Path(vi)
    job.set_stage("translating")
    vi_segs = translate.translate_segments(segs)
    vi = write_srt(vi_segs, str(d / "vi.srt"))
    return vi_segs, Path(vi)


async def run_job(job: Job) -> Job:
    d = SETTINGS.jobs_dir / job.id
    d.mkdir(parents=True, exist_ok=True)
    try:
        await asyncio.to_thread(require_gpu)
        if job.uploaded and job.video and job.video.exists():
            # File upload qua Discord: bo qua yt-dlp, di thang vao Demucs/ASR
            job.status, job.progress, job.pct = "separating", "📁 Da nhan file upload, bo qua tai video.", 15
        else:
            job.set_stage("downloading")
            job.video = await asyncio.to_thread(download, job.url, d)

        if job.mode == "separate":
            full = await asyncio.to_thread(_extract_full_audio, job.video, d / "audio_full.wav")
            job.set_stage("separating")
            vocals_wav, music_wav = await asyncio.to_thread(demucs.separate, full, d / "demucs")
            job.vocals = await asyncio.to_thread(_to_mp3, vocals_wav, d / "vocals.mp3")
            job.music = await asyncio.to_thread(_to_mp3, music_wav, d / "music.mp3")
            job.set_stage("done")
            return job

        if job.mode == "dub" and job.subs_file and job.subs_file.exists():
            # /dub voi file phu de da dich: bo qua ASR + dich, dung thang
            # moc + loi trong file user dua. Chi can Demucs lay nhac nen (neu bat).
            job.status, job.progress, job.pct = "translating", "📄 Dung file phu de da dich, bo qua ASR/dich.", 60
            vi_segs = read_srt(str(job.subs_file))
            if not vi_segs:
                raise RuntimeError("File phu de da dich rong hoac sai dinh dang SRT.")
            job.vi_srt = d / "vi.srt"
            job.vi_srt.write_text(job.subs_file.read_text(encoding="utf-8"), encoding="utf-8")
            job.srt = None  # khong co ASR nen khong co orig.srt
            music_wav = None
            if job.demucs_enabled:
                full = await asyncio.to_thread(_extract_full_audio, job.video, d / "audio_full.wav")
                job.set_stage("separating")
                try:
                    _voc, music_wav = await asyncio.to_thread(demucs.separate, full, d / "demucs")
                except Exception as e:
                    job.warning += f"Demucs that bai, long tieng khong co nhac nen: {str(e)[:200]}. "
        else:
            segs, _vocals, music_wav = await asyncio.to_thread(_asr_with_demucs, job, d)
            vi_segs, vi_path = await asyncio.to_thread(_translate_if_en, job, segs, d)
            job.srt, job.vi_srt = d / "orig.srt", vi_path

        if job.mode == "sub":
            job.set_stage("done")
            return job

        # /dub: TTS tieng Viet -> fit slot -> tron nhac -> mux
        job.set_stage("tts")
        tts_wavs = await asyncio.to_thread(tts.synth_segments, vi_segs, d / "tts", job.voice)
        job.set_stage("muxing")
        total_s = max(s.end for s in vi_segs)
        dub_audio = await asyncio.to_thread(
            mux.build_dubbed_audio, vi_segs, tts_wavs, total_s, d / "mux", music_wav)
        job.dubbed = await asyncio.to_thread(
            mux.mux_video, job.video, dub_audio, d / "dubbed.mp4")
        job.set_stage("done")
        return job
    except Exception as e:
        job.status, job.error = "failed", str(e)[:1000]
        print(f"[job {job.id}] FAILED at {job.status}: {job.error}", flush=True)
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
