# Auto-Dub Bot — Discord + Tesla T4

Lồng tiếng tự động video YouTube / Facebook. Bot Discord, 1 job chạy tại 1 thời điểm.

> Lưu ý: đây là bản làm lại theo yêu cầu mới (Discord bot). Bản web cũ đã bỏ ngày 11/11, không dùng lại code cũ.

## 1. Sơ đồ kiến trúc pipeline (text)

```
User Discord
  /dub <url>  /sub <url>
      |
      v
bot.py (discord.py, defer, followup) --enqueue--> asyncio.Queue (Worker: 1 job)
      |
      v
[1] downloader.py : yt-dlp -> video.mp4 (<=1080p)
      | 403 -> update yt-dlp, cookies.txt, player_client=android
      v
[2] ffmpeg : tach audio 16kHz mono -> audio16k.wav
      v
[3] asr.py : faster-whisper
      |  EN: large-v3, fp16, cuda
      |  VI: PhoWhisper-large (CT2, xem scripts/) -- chua convert thi fallback large-v3 lang=vi
      |  unload model + empty_cache sau ASR
      v
 segments[] (start, end, text)  -->  orig.srt
      |
      +-- /sub: DUNG O DAY, tra .srt
      |
      v
[4] translate.py : NLLB-200-distilled-600M, CUDA fp16, batch 8
      |  src==tgt thi bo qua. Khong dung Google/deep-translator nua.
      v
 dub.srt (giu nguyen moc thoi gian)
      v
[5] tts.py : VieNeu v3 Turbo infer_batch(batch_size=8, fp16) — CA VI + EN
      |  (VieNeu song ngu EN-VI, khong dung edge-tts cloud nua)
      |  unload TTS sau xong
      v
[6] mux.py : fit_to_slot() -- toc do TTS kep 0.85-1.15x, thieu thi dem silence,
      |       thua thi cat -> dat clip dung khung SRT -> ffmpeg amix voi am goc 0.15
      v
 dubbed.mp4 + dub.srt
      |
      v
bot.py: <=25MB gui file truc tiep, >25MB bao duong dan VPS + up host ngoai
```

TAT CA MODEL AI DEU CHAY TREN GPU (khong fallback CPU/cloud):
| Buoc | Model | GPU |
|---|---|---|
| ASR | faster-whisper large-v3 / PhoWhisper-CT2 | CUDA fp16, ~6GB |
| Dich | NLLB-200-distilled-600M | CUDA fp16, ~1.2GB |
| TTS vi+en | VieNeu v3 Turbo `vieneu[cuda]` | CUDA fp16, ~2-3GB |
Chay tuan tu + unload sau moi buoc nen dinh ~6-8GB, khong giu 2 model cung luc. Bot fail nhanh neu khong co CUDA (`require_gpu()` o pipeline).
Ngoai le duy nhat khong phai AI: yt-dlp tai video + ffmpeg/pydub cat/ghep audio — viec nhe, khong co ban GPU, giu nguyen CPU.

Đính chính nhỏ: T4 thật là 16GB VRAM, không phải 12GB. Thiết kế theo ngân sách 12GB nên vẫn an toàn trên T4.

## 2. Cấu trúc thư mục

```
auto-dub-bot/
  bot.py                 # entry, /dub /sub /queue, Queue + Worker
  requirements.txt
  .env.example           # copy thanh .env, dien DISCORD_TOKEN
  dub/
    config.py            # Settings tu .env, khong hardcode token
    downloader.py        # yt-dlp + ffmpeg tach audio
    asr.py               # faster-whisper / PhoWhisper-CT2
    srt.py               # Segment, doc/ghi SRT
    translate.py         # EN->VI theo segment
    tts.py               # VieNeu GPU (ca vi + en)
    mux.py               # fit_to_slot + ffmpeg ghep
    pipeline.py          # Job + Worker tuan tu
  scripts/
    convert_phowhisper_ct2.sh   # convert PhoWhisper 1 lan
  systemd/
    dub-bot.service
  cookies/               # bo cookies.txt vao day (Facebook rieng tu), khong commit
  data/jobs/<job-id>/    # video, srt, tts, dubbed.mp4 theo job
```

## 3. Cài đặt (VPS Linux, T4)

```bash
# 1. Driver + CUDA (Ubuntu 22.04)
sudo apt update && sudo apt install -y ffmpeg espeak-ng python3.12 python3.12-venv git
# Cai driver NVIDIA 535+ / CUDA 12.8 tu trang NVIDIA, roi:
nvidia-smi   # phai thay T4

# 2. Code + venv
git clone <repo> auto-dub-bot && cd auto-dub-bot
python3.12 -m venv .venv && source .venv/bin/activate
pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
# requirements.txt da dung vieneu[cuda]==3.7.1 (khong phai vieneu thuong,
# ban thuong chi chay CPU/ONNX). Extra "gpu" khong ton tai tren PyPI.
cp .env.example .env   # dien DISCORD_TOKEN

# 3. PhoWhisper tieng Viet (1 lan, neu can)
bash scripts/convert_phowhisper_ct2.sh
# -> .env: PHOWHISPER_CT2_DIR=models/phowhisper-large-ct2

# 4. Chay thu
python bot.py
# Test nhanh: /sub <link youtube ngan> trong server test
```

## 4. Triển khai systemd

```bash
sudo cp systemd/dub-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dub-bot
journalctl -u dub-bot -f
```

File `systemd/dub-bot.service` đã viết sẵn, sửa `User=` và `WorkingDirectory=` theo VPS của mày.

## 5. Lỗi thường gặp

| Lỗi | Cách xử |
|---|---|
| yt-dlp 403 | `pip install -U yt-dlp`, thêm `cookies/cookies.txt` (lay bang extension Get cookies.txt), thử `--extractor-args youtube:player_client=android` (đã có sẵn trong code) |
| Facebook riêng tư | Bắt buộc cookies.txt từ tài khoản có quyền xem video đó |
| OOM T4 | Giảm `VIENEU_BATCH_SIZE=4`, Whisper xuống `large-v3` vẫn giữ, không chạy job thứ 2 |
| VieNeu lỗi import torch | Cài torch cu128 trước requirements (xem mục 3), kiểm tra `python -c "import torch; print(torch.cuda.is_available())"` |
| PhoWhisper không load | Chưa convert CT2 — chạy `scripts/convert_phowhisper_ct2.sh`, hoặc để trống `PHOWHISPER_CT2_DIR` để fallback large-v3 |
| Discord file >25MB | Bot chỉ báo đường dẫn VPS, tự up host ngoài rồi gửi link |
| Bot không thấy lệnh | Sync global mất ~1h lần đầu — đặt `GUILD_ID` trong .env để test nhanh |

## 6. Giả định đã chốt (theo Karpathy: nói rõ trước khi code)

- Dịch mặc định EN→VI; video tiếng Việt thì `/dub <url> src:vi tgt:vi` (không dịch, chỉ lồng lại).
- VieNeu SDK hiện tại không có tham số `max_streams=8` — dùng `infer_batch(batch_size=8)`.
- Tat ca model AI tren GPU, khong fallback CPU/cloud: dich NLLB GPU, TTS VieNeu GPU (ca en), ASR Whisper GPU. Da bo edge-tts, deep-translator, KorvaTTS.
- Chưa test trên T4 thật (máy này không có GPU) — cần chạy thử `/sub` video ngắn trước rồi mới `/dub`. Rieng NLLB cung chua test that: can chay thu dich 1-2 cau truoc khi dich video dai.
