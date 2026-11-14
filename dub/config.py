"""Config duy nhat cho ca bot. Doc tu .env, khong hardcode token."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    discord_token: str = os.environ["DISCORD_TOKEN"]  # bat buoc, thieu -> crash luc khoi dong, dung y
    guild_id: int | None = int(os.environ["GUILD_ID"]) if os.getenv("GUILD_ID") else None
    jobs_dir: Path = ROOT / "data" / "jobs"
    cookies_file: Path = ROOT / "cookies" / "cookies.txt"  # co thi dung, khong co thi bo qua
    max_duration_s: int = int(os.getenv("MAX_DURATION_S", "1800"))  # 30 phut
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "25"))  # gioi han Discord user noi
    # ASR
    whisper_en: str = os.getenv("WHISPER_EN", "large-v3")
    phowhisper_ct2_dir: str = os.getenv("PHOWHISPER_CT2_DIR", "")  # vd: models/phowhisper-large-ct2
    # Dich: NLLB-200-distilled-600M tren GPU (CUDA, fp16)
    nllb_model: str = os.getenv("NLLB_MODEL", "facebook/nllb-200-distilled-600M")
    # TTS (ca vi + en): vieneu v3 Turbo, 48kHz, song ngu EN-VI, GPU PyTorch.
    vieneu_voice: str = os.getenv("VIENEU_VOICE", "nu-mien-bac-01")
    vieneu_precision: str = os.getenv("VIENEU_PRECISION", "fp16")  # fp16 tren T4, khong dung bf16
    vieneu_batch_size: int = int(os.getenv("VIENEU_BATCH_SIZE", "8"))  # batch_size=8-16, khong co max_streams
    # Ghep tieng: am goc de nho duoi lop long tieng, 0.0 = tat han
    original_volume: float = float(os.getenv("ORIGINAL_VOLUME", "0.15"))


SETTINGS = Settings()


def require_gpu() -> None:
    """Bot chi chay tren GPU — fail nhanh neu khong co CUDA, khong fallback CPU."""
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("Khong thay GPU (CUDA). Bot nay chi chay tren GPU, khong chay CPU.")
    print(f"GPU: {torch.cuda.get_device_name(0)} "
          f"({torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB VRAM)")
