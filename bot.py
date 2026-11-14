"""Bot Discord long tieng + phu de.
  /sub <url|file>  -> orig.srt (goc) + vi.srt (tieng Viet rieng)
  /dub <url|file> [subs=.srt da dich] [demucs=true/false] -> dubbed.mp4 + orig.srt + vi.srt
  /separate <url>  -> vocals.mp3 (giong) + music.mp3 (nhac nen, Demucs)
  /cookies ...     -> upload cookies.txt khi bi chan 403
Tien trinh: embed co thanh ██████░░░░ 62% + ten buoc, edit lien tuc.
Chay: python bot.py  (token trong .env, khong hardcode)
"""
import asyncio
import faulthandler, signal

import discord
from discord import app_commands

from dub import cookies as cookie_store
from dub.config import SETTINGS
from dub.pipeline import Job, Worker
from dub.progress import bar, embed_for

faulthandler.enable()
faulthandler.register(signal.SIGUSR1, chain=False)

worker = Worker()
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

MAX_DISCORD_BYTES = 25 * 1024 * 1024  # gioi han file dinh kem Discord (khong Nitro)
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # file upload toi da 500MB (gioi han Nitro)
ALLOWED_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".mp3", ".wav", ".m4a", ".ogg", ".flac"}


def _upload_error(file: discord.Attachment) -> str | None:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTS:
        return f"❌ File `{file.filename}` khong ho tro — chi nhan: {', '.join(sorted(ALLOWED_EXTS))}."
    if file.size > MAX_UPLOAD_BYTES:
        return f"❌ File qua lon ({file.size // 1048576}MB > 500MB)."
    return None


async def _wait_with_progress(itx: discord.Interaction, job: Job):
    """Gui embed tien trinh roi edit moi 4s cho toi khi xong / loi."""
    msg = await itx.followup.send(embed=embed_for(job.id, "⏳ Dang cho trong hang doi...", 0, job.mode))
    last_pct = -1
    while job.status not in ("done", "failed"):
        await asyncio.sleep(4)
        if job.pct != last_pct:
            last_pct = job.pct
            try:
                await msg.edit(embed=embed_for(job.id, job.progress, job.pct, job.mode))
            except discord.HTTPException:
                pass
    if job.status == "failed":
        await msg.edit(embed=discord.Embed(
            title=f"❌ Job `{job.id}` loi", description=job.error[:1500], color=0xED4245))
        return
    files, notes = [], []
    for path, label in [(job.dubbed, "dubbed.mp4"), (job.srt, "orig.srt"),
                        (job.vi_srt, "vi.srt"), (job.vocals, "vocals.mp3"),
                        (job.music, "music.mp3")]:
        if path and path.exists():
            if path.stat().st_size > MAX_DISCORD_BYTES:
                notes.append(f"⚠️ `{label}` qua 25MB ({path.stat().st_size // 1048576}MB), Discord khong gui duoc — file nam o `data/jobs/{job.id}/` tren VPS.")
            else:
                files.append(discord.File(path))
    done = discord.Embed(
        title=f"✅ Xong `{job.id}`",
        description=f"`{bar(100)}`\n{job.progress}" + (f"\n⚠️ {job.warning}" if job.warning else ""),
        color=0x57F287)
    if notes:
        done.add_field(name="Luu y", value="\n".join(notes), inline=False)
    await msg.edit(embed=done)
    if files:
        await itx.followup.send(files=files)


async def _enqueue(itx: discord.Interaction, mode: str, url: str | None = None,
                 file: discord.Attachment | None = None, lang: str = "en",
                 subs: discord.Attachment | None = None, demucs: bool = True):
    await itx.response.defer(thinking=True)
    if file is None and not url:
        await itx.followup.send("❌ Dien `url` hoac dinh kem `file` video/audio — phai co 1 trong 2.")
        return
    job = Job(url=url or "", src_lang=lang, mode=mode, demucs_enabled=demucs)
    d = SETTINGS.jobs_dir / job.id
    d.mkdir(parents=True, exist_ok=True)
    if file is not None:
        # Uu tien file upload: tai file ve truoc roi moi enqueue
        err = _upload_error(file)
        if err:
            await itx.followup.send(err)
            return
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()
        job.video = d / f"upload{ext}"
        job.video.write_bytes(await file.read())
        job.uploaded = True
    if subs is not None:
        # File phu de da dich (.srt): chi /dub dung, bo qua ASR + dich
        if not subs.filename.lower().endswith(".srt"):
            await itx.followup.send("❌ File phu de phai la `.srt`.")
            return
        if subs.size > 5 * 1024 * 1024:
            await itx.followup.send("❌ File phu de qua lon (>5MB).")
            return
        job.subs_file = d / "provided_vi.srt"
        job.subs_file.write_bytes(await subs.read())
    await worker.q.put(job)
    await _wait_with_progress(itx, job)


@tree.command(name="sub", description="Xuat phu de: orig.srt goc + vi.srt tieng Viet rieng")
@app_commands.describe(url="Link YouTube / Facebook (hoac de trong neu upload file)",
                       file="Upload truc tiep file video/audio thay cho url",
                       lang="Ngon ngu noi trong video: en hoac vi",
                       demucs="Bat/tat Demucs tach giong truoc khi ASR (mac dinh: bat)")
async def sub(itx: discord.Interaction, url: str | None = None,
              file: discord.Attachment | None = None, lang: str = "en",
              demucs: bool = True):
    await _enqueue(itx, "sub", url, file, lang, demucs=demucs)


@tree.command(name="dub", description="Long tieng sang tieng Viet: dubbed.mp4 + orig.srt + vi.srt")
@app_commands.describe(url="Link YouTube / Facebook (hoac de trong neu upload file)",
                       file="Upload truc tiep file video/audio thay cho url",
                       lang="Ngon ngu goc trong video: en hoac vi",
                       subs="File .srt da dich san — co thi bo qua ASR/dich, doc thang file nay",
                       demucs="Bat/tat Demucs tach nhac nen (mac dinh: bat)")
async def dub(itx: discord.Interaction, url: str | None = None,
              file: discord.Attachment | None = None, lang: str = "en",
              subs: discord.Attachment | None = None, demucs: bool = True):
    await _enqueue(itx, "dub", url, file, lang, subs=subs, demucs=demucs)


@tree.command(name="separate", description="Demucs: tach giong (vocals.mp3) va nhac nen (music.mp3) tu video")
@app_commands.describe(url="Link YouTube / Facebook (hoac de trong neu upload file)",
                       file="Upload truc tiep file video/audio thay cho url")
async def separate(itx: discord.Interaction, url: str | None = None,
                   file: discord.Attachment | None = None):
    await _enqueue(itx, "separate", url, file, "en")


@tree.command(name="cookies", description="Upload file cookies.txt de tai video bi chan 403 / video rieng tu")
@app_commands.describe(file="File cookies.txt xuat tu trinh duyet (extension 'Get cookies.txt LOCALLY')")
async def cookies_cmd(itx: discord.Interaction, file: discord.Attachment):
    await itx.response.defer(thinking=True, ephemeral=True)  # rieng tu: chi minh thay
    if not file.filename.endswith(".txt"):
        await itx.followup.send("❌ Chi nhan file `.txt` (cookies.txt dang Netscape).")
        return
    if file.size > cookie_store.MAX_BYTES:
        await itx.followup.send("❌ File cookie qua lon (>1MB).")
        return
    try:
        text = (await file.read()).decode("utf-8")
        info = cookie_store.save(text)
    except ValueError as e:
        await itx.followup.send(f"❌ {e}")
        return
    except Exception as e:
        await itx.followup.send(f"❌ Khong doc duoc file: {e}")
        return
    domains = ", ".join(sorted(info.domains)) or "khong ro"
    warn = ""
    if not any(d in ("youtube.com", "facebook.com") for d in info.domains):
        warn = "\n⚠️ Khong thay cookie youtube.com / facebook.com — kiem tra lai xem co xuat nham trang khac khong."
    await itx.followup.send(
        f"✅ Da luu cookie: {info.valid} cookie con han ({info.expired} het han, bo qua).\n"
        f"Domain: {domains}{warn}\n"
        f"Gio /sub lai link bi chan thu xem. Dung /cookies-clear de xoa khi khong can nua.")


@tree.command(name="cookies-status", description="Xem cookie da luu hay chua (khong hien gia tri cookie)")
async def cookies_status(itx: discord.Interaction):
    await itx.response.defer(thinking=True, ephemeral=True)
    info = cookie_store.status()
    if info is None:
        await itx.followup.send("Chua co cookie nao. Upload bang /cookies khi bi chan 403.")
        return
    await itx.followup.send(
        f"Cookie da luu: {info.valid} con han, {info.expired} het han.\n"
        f"Domain: {', '.join(sorted(info.domains)) or 'khong ro'}")


@tree.command(name="cookies-clear", description="Xoa file cookie da luu tren VPS")
async def cookies_clear(itx: discord.Interaction):
    await itx.response.defer(thinking=True, ephemeral=True)
    if cookie_store.clear():
        await itx.followup.send("✅ Da xoa cookie.")
    else:
        await itx.followup.send("Khong co cookie nao de xoa.")


@tree.command(name="queue", description="Xem hang doi")
async def queue(itx: discord.Interaction):
    cur = f"{worker.current.id} ({worker.current.status} {worker.current.pct}%)" if worker.current else "khong co"
    await itx.response.send_message(f"Dang chay: {cur}\nCho: {worker.q.qsize()} job")


@bot.event
async def on_ready():
    asyncio.create_task(worker.start())
    if SETTINGS.guild_id:
        tree.copy_global_to(guild=discord.Object(id=SETTINGS.guild_id))
        synced = await tree.sync(guild=discord.Object(id=SETTINGS.guild_id))
        print(f"Guild sync: {len(synced)} commands -> {[c.name for c in synced]}")
    else:
        synced = await tree.sync()
        print(f"Global sync: {len(synced)} commands")
    print(f"Bot san sang: {bot.user} - /sub /dub /separate /cookies /queue")


if __name__ == "__main__":
    bot.run(SETTINGS.discord_token)
