"""Thanh tien trinh 'native' cho Discord: embed + thanh khoi Unicode.
Discord khong co widget progress that, cach dep nhat la embed co thanh
██████████░░░░ 62% + ten buoc, edit message cu moi vai giay.
"""
BAR_WIDTH = 12


def bar(pct: int, width: int = BAR_WIDTH) -> str:
    pct = max(0, min(100, pct))
    filled = int(round(pct / 100 * width))
    return "█" * filled + "░" * (width - filled) + f" {pct}%"


def embed_for(job_id: str, stage: str, pct: int, mode: str):
    import discord

    e = discord.Embed(
        title=f"🎬 {'Long tieng' if mode == 'dub' else 'Phu de' if mode == 'sub' else 'Tach am thanh'} — `{job_id}`",
        description=f"**{stage}**\n`{bar(pct)}`",
        color=0x5865F2,
    )
    e.set_footer(text="Bot chay 1 job/lan tren T4 — doi chut nhe")
    return e
