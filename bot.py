"""Bot Discord chi lam phu de: /sub <url> -> file .srt (khong dich, khong long tieng).
Chay: python bot.py  (token trong .env, khong hardcode)
"""
import asyncio

import discord
from discord import app_commands

from dub import cookies as cookie_store
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
    cur = f"{worker.current.id} ({worker.current.status})" if worker.current else "khong co"
    await itx.response.send_message(f"Dang chay: {cur}\nCho: {worker.q.qsize()} job")


@bot.event
async def on_ready():
    asyncio.create_task(worker.start())
    if SETTINGS.guild_id:
        await tree.sync(guild=discord.Object(id=SETTINGS.guild_id))
    else:
        await tree.sync()  # global sync cham ~1h lan dau
    print(f"Bot san sang: {bot.user} - /sub /cookies /cookies-status /cookies-clear /queue")


if __name__ == "__main__":
    bot.run(SETTINGS.discord_token)
