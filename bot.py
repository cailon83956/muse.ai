"""Bot Discord chi lam phu de: /sub <url> -> file .srt (khong dich, khong long tieng).
Chay: python bot.py  (token trong .env, khong hardcode)
"""
import asyncio

import discord
from discord import app_commands

from dub.config import SETTINGS
from dub.pipeline import Job, Worker

worker = Worker()
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


async def _wait_and_reply(itx: discord.Interaction, job: Job):
    while job.status not in ("done", "failed"):
        await asyncio.sleep(5)
    if job.status == "failed":
        await itx.followup.send(f"❌ Job `{job.id}` loi: {job.error[:1500]}")
        return
    files = [discord.File(job.srt)] if job.srt and job.srt.exists() else []
    await itx.followup.send(f"✅ Xong `{job.id}` - {job.progress}", files=files)


@tree.command(name="sub", description="Xuat file phu de .srt goc tu video YouTube/Facebook")
@app_commands.describe(url="Link YouTube / Facebook", lang="Ngon ngu noi trong video: en hoac vi")
async def sub(itx: discord.Interaction, url: str, lang: str = "en"):
    await itx.response.defer(thinking=True)
    job = Job(url=url, src_lang=lang)
    await worker.q.put(job)
    await itx.followup.send(f"📝 Da nhan job `{job.id}` - dang cho (vi tri {worker.q.qsize()}).")
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
    print(f"Bot san sang: {bot.user} - /sub /queue")


if __name__ == "__main__":
    bot.run(SETTINGS.discord_token)
