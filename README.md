# Sub Bot — Discord, chi xuat file phu de .srt

Bot Discord don gian: `/sub <url>` -> file `.srt` goc. Khong dich, khong long tieng, khong ghep video.

## Pipeline

```
Discord /sub <url> --enqueue--> asyncio.Queue (1 job/lan)
  -> yt-dlp (YouTube/Facebook, <=1080p, cookies.txt neu co)
  -> ffmpeg tach audio 16kHz mono
  -> faster-whisper tren GPU: EN large-v3 fp16 / VI PhoWhisper-CT2
  -> orig.srt (giu nguyen ngon ngu goc, khong dich)
  -> gui file .srt ve Discord
```

VRAM: Whisper large-v3 fp16 ~6GB tren T4. Bot fail nhanh neu khong co CUDA.

## Cau truc

```
auto-dub-bot/
  bot.py                 # entry, /sub /queue
  requirements.txt       # chi discord.py, yt-dlp, faster-whisper
  .env.example           # copy thanh .env, dien DISCORD_TOKEN
  dub/
    config.py            # Settings tu .env
    downloader.py        # yt-dlp + ffmpeg tach audio
    asr.py               # faster-whisper / PhoWhisper-CT2
    srt.py               # Segment, doc/ghi SRT
    pipeline.py          # Job + Worker tuan tu
  scripts/
    convert_phowhisper_ct2.sh   # convert PhoWhisper 1 lan
  systemd/
    dub-bot.service
  cookies/               # bo cookies.txt vao day (Facebook rieng tu)
  data/jobs/<job-id>/    # video, srt theo job
```

## Upload cookie khi bi chan 403

Khi `/sub` bao loi 403 / "Sign in to confirm" / video rieng tu khong tai duoc:

1. Dang nhap YouTube/Facebook tren Chrome, cai extension **"Get cookies.txt LOCALLY"**, Export ra `cookies.txt`.
2. Tren Discord go `/cookies` + dinh kem file `cookies.txt` (lenh rieng tu, chi minh thay).
3. Bot bao so cookie con han + domain (youtube.com / facebook.com) la xong, `/sub` lai link do.
4. Kiem tra bang `/cookies-status`, xoa bang `/cookies-clear` khi khong can.

Cookie luu o `cookies/cookies.txt` tren VPS, chmod 0600, khong commit len git, khong bao gio hien gia tri ra chat. Het han hoac doi mat khau thi xuat lai file moi.

## Cai dat (VPS Linux, T4)

```bash
sudo apt update && sudo apt install -y ffmpeg python3.12 python3.12-venv git
nvidia-smi   # phai thay T4
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # dien DISCORD_TOKEN
python bot.py
# Test: /sub <link youtube ngan>
```

PhoWhisper tieng Viet (1 lan, neu can):
```bash
bash scripts/convert_phowhisper_ct2.sh
# -> .env: PHOWHISPER_CT2_DIR=models/phowhisper-large-ct2
```

systemd: sua `User=` / `WorkingDirectory=` trong `systemd/dub-bot.service`, roi `systemctl enable --now dub-bot`.

## Loi thuong gap

| Loi | Cach xu |
|---|---|
| yt-dlp 403 | `pip install -U yt-dlp`, them `cookies/cookies.txt`, da co san `player_client=android` |
| Facebook rieng tu | Bat buoc cookies.txt tu tai khoan co quyen xem video do |
| OOM T4 | Khong chay 2 job song song (bot da khoa 1 job/lan) |
| PhoWhisper khong load | Chua convert CT2 — chay script tren, hoac de trong `PHOWHISPER_CT2_DIR` de fallback large-v3 |
| Bot khong thay lenh | Sync global mat ~1h lan dau — dat `GUILD_ID` trong .env de test nhanh |

## Lich su rut gon

- Ban dau la bot long tieng day du (/dub + /sub, dich NLLB + TTS VieNeu GPU).
- 2026-11-14: bo dich, bo long tieng — chi giu xuat .srt. Da xoa `translate.py`, `tts.py`, `mux.py` va cac dep chi phuc vu dich/long tieng (torch, transformers, vieneu, NLLB, edge-tts, deep-translator).
- Chua test tren T4 that — can chay thu `/sub` video ngan truoc.
