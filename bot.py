"""Bot Discord: /dub, /sub. Chi enqueue + tra ket qua, moi viec nang o Worker.
Chay: python bot.py  (token trong .env, khong hardcode)
"""
import asyncio
from pathlib import Path

import discord
from discord import app_commands

from dub.config import SETTINGS
from dub.pipeline import Job, Worker

worker = Worker()
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


def _mb(p: Path) -> float:
    return p.stat().st_size / 1024 / 1024


async def _wait_and_reply(itx: discord.Interaction, job: Job):
    while job.status not in ("done", "failed"):
        await asyncio.sleep(5)
        # Cap nhat tien do moi 30s de khong spam API Discord
    if job.status == "failed":
        await itx.followup.send(f"❌ Job `{job.id}` loi: {job.error[:1500]}")
        return
    files = []
    if job.srt and job.srt.exists():
        files.append(discord.File(job.srt))
    if job.mode == "dub" and job.out_mp4 and job.out_mp4.exists():
        if _mb(job.out_mp4) <= SETTINGS.max_upload_mb:
            files.append(discord.File(job.out_mp4))
        else:
            await itx.followup.send(
                f"⚠️ MP4 {_mb(job.out_mp4):.1f}MB > {SETTINGS.max_upload_mb}MB nen khong gui truc tiep duoc.\n"
                f"File nam tren VPS: `{job.out_mp4}` - up len host ngoai (vd: rclone / file-hosting) roi gui link.",
                files=files)
            return
    await itx.followup.send(f"✅ Xong `{job.id}` - {job.progress}", files=files)


@tree.command(name="dub", description="Long tieng video YouTube/Facebook sang tieng Viet (mac dinh)")
@app_commands.describe(url="Link YouTube / Facebook", src="Ngon ngu goc: en hoac vi", tgt="Ngon ngu dich: vi hoac en")
async def dub(itx: discord.Interaction, url: str, src: str = "en", tgt: str = "vi"):
    await itx.response.defer(thinking=True)
    job = Job(url=url, mode="dub", src_lang=src, tgt_lang=tgt)
    await worker.q.put(job)
    pos = worker.q.qsize()
    await itx.followup.send(f"🎬 Da nhan job `{job.id}` - dang cho (vi tri {pos}, T4 chay 1 job/lan).")
    await _wait_and_reply(itx, job)


@tree.command(name="sub", description="Chi xuat SRT goc, khong long tieng")
@app_commands.describe(url="Link YouTube / Facebook", lang="Ngon ngu noi trong video: en hoac vi")
async def sub(itx: discord.Interaction, url: str, lang: str = "en"):
    await itx.response.defer(thinking=True)
    job = Job(url=url, mode="sub", src_lang=lang, tgt_lang=lang)
    await worker.q.put(job)
    await itx.followup.send(f"📝 Da nhan job `{job.id}` - chi lam SRT.")
    await _wait_and_reply(itx, job)


@tree.command(name="queue", description="Xem hang doi")
async def queue(itx: discord.Interaction):
    cur = f"{worker.current.id} ({worker.current.status})" if worker.current else "khong co"
    await itx.response.send_message(f"Dang chay: {cur}\nCho: {worker.q.qsize()} job")


@bot.event
async def on_ready():
    asyncio.create_task(worker.start())
    if SETTINGS.guild_id:
        await tree.sync(guild=discord.Object(id=SETTINGS.guild_id))
    else:
        await tree.sync()  # global sync cham ~1h lan dau
    print(f"Bot san sang: {bot.user} - /dub /sub /queue")


if __name__ == "__main__":
    bot.run(SETTINGS.discord_token)
