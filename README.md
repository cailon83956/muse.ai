# Dub Bot — Discord, long tieng + phu de (T4 GPU)

Bot Discord:
- `/sub <url>` — xuat phu de rieng biet: `orig.srt` (goc) + `vi.srt` (tieng Viet)
- `/dub <url>` — long tieng sang tieng Viet: `dubbed.mp4` + `orig.srt` + `vi.srt`
- `/separate <url>` — Demucs tach am thanh goc: `vocals.mp3` (giong) + `music.mp3` (nhac nen)
- `/cookies` — upload `cookies.txt` khi bi chan 403 / video rieng tu

## Pipeline

```
Discord /sub /dub /separate --enqueue--> asyncio.Queue (1 job/lan)
  -> yt-dlp (YouTube/Facebook, <=1080p, cookies.txt neu co, player_client=android)
  -> ffmpeg tach audio 44.1kHz stereo
  -> Demucs htdemucs --two-stems=vocals -> vocals.wav + no_vocals.wav (nhac)
     (that bai -> fallback audio goc, job van chay, co warning)
  -> faster-whisper tren GPU tren vocals: EN large-v3 fp16 / VI PhoWhisper-CT2
  -> align khop mieng (word timestamps + snap nang luong, xem duoi)
  -> dich EN->VI bang NLLB-200-distilled-600M GPU fp16 -> vi.srt rieng
     (nguon VI thi vi.srt = orig.srt, khong dich)
  -> /sub dung o day
  -> /dub: VieNeu v3 Turbo GPU doc vi.srt -> fit slot 0.85-1.15x (atempo)
     -> tron giong + nhac nen (nhac giam con 25%) -> mux video goc -> dubbed.mp4
```

Tien trinh: embed Discord co thanh `██████████░░░░ 62%` + ten buoc, edit lien tuc moi 4s.
File >25MB Discord khong gui duoc — bot bao va chi duong dan tren VPS (`data/jobs/<id>/`).

VRAM: Whisper ~6GB, NLLB ~1.5GB, VieNeu ~2-3GB, Demucs ~2-3GB (chay subprocess, xong la giai phong). Bot fail nhanh neu khong co CUDA.

## Cau truc

```
auto-dub-bot/
  bot.py                 # entry, /sub /dub /separate /cookies /queue + thanh tien trinh
  requirements.txt       # discord.py, yt-dlp, faster-whisper, torch, demucs, transformers, vieneu[cuda]
  .env.example           # copy thanh .env, dien DISCORD_TOKEN
  dub/
    config.py            # Settings tu .env
    downloader.py        # yt-dlp + ffmpeg tach audio (yt-dlp resolve theo venv, fix opencode)
    demucs.py            # tach giong/nhac bang subprocess python -m demucs
    asr.py               # faster-whisper / PhoWhisper-CT2
    align.py             # snap moc phu de khop mieng (stdlib)
    translate.py         # NLLB EN->VI
    tts.py               # VieNeu GPU
    mux.py               # fit slot, timeline giong, tron nhac, mux video
    srt.py               # Segment, doc/ghi SRT
    cookies.py           # validate + luu cookies.txt
    progress.py          # thanh tien trinh embed
    pipeline.py          # Job + Worker tuan tu
  scripts/
    convert_phowhisper_ct2.sh   # convert PhoWhisper 1 lan
  systemd/
    dub-bot.service
  cookies/               # bo cookies.txt vao day (Facebook rieng tu)
  data/jobs/<job-id>/    # video, srt, mp4 theo job
```

## Fix lech mieng (timing phu de khop mieng)

1. **Word timestamps** — faster-whisper `word_timestamps=True`, moc lay tu tu dau/cuoi thay vi ca segment.
2. **Snap bang nang luong that** — `dub/align.py`, chi dung stdlib (`wave` + `math`): RMS moi 10ms, nguong = 25% RMS dinh cua chinh doan do, tim khung noi dau/cuoi trong cua so ±0.3s quanh moc Whisper. Cua so khong lan sang cau ke ben.
3. **Lead/tail** — tru 80ms dau, cong 50ms cuoi, kep khong chong cau sau.

Test tong hop (im 1s + tone 1s + im 0.5s + tone 1s): segment thua im 0.3s dau/cuoi duoc can ve dung 0.92→2.05 va 2.42→3.55; doan im hoan toan thi giu nguyen moc cu. Chua test tren video that / T4.

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
pip install -r requirements.txt   # nang, cai 1 lan (torch/demucs/vieneu)
cp .env.example .env   # dien DISCORD_TOKEN
python bot.py
# Test: /sub <link youtube ngan> truoc, roi /dub, roi /separate
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
| Demucs that bai | Job van chay bang audio goc (co warning); kiem tra `pip show demucs` + VRAM |
| Bot khong thay lenh | Sync global mat ~1h lan dau — dat `GUILD_ID` trong .env de test nhanh |
| File >25MB | Discord khong gui duoc, lay file o `data/jobs/<id>/` tren VPS |

## Lich su

- Ban dau la bot long tieng day du, rut xuong chi /sub (2026-11-14), roi khoi phuc lai /dub + them /separate (Demucs) + thanh tien trinh embed.
- Fix cua opencode 2026-11-14 da giu lai: yt-dlp resolve theo venv python, pin `av==12.3.0`.
- Chua test tren T4 that (Demucs / NLLB / VieNeu that) — can chay thu video ngan truoc.
