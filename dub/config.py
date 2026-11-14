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
    # ASR tren GPU (faster-whisper / CTranslate2)
    whisper_en: str = os.getenv("WHISPER_EN", "large-v3")
    phowhisper_ct2_dir: str = os.getenv("PHOWHISPER_CT2_DIR", "")  # vd: models/phowhisper-large-ct2
    # Long tieng (GPU): dich NLLB, TTS VieNeu, tach Demucs
    nllb_model: str = os.getenv("NLLB_MODEL", "facebook/nllb-200-distilled-600M")
    demucs_model: str = os.getenv("DEMUCS_MODEL", "htdemucs")
    vieneu_voice: str = os.getenv("VIENEU_VOICE", "")  # de trong = giong mac dinh
    # URL goc cua file server (vd: http://34.142.155.8:8000). De trong = dung gofile.io.
    file_base_url: str = os.getenv("FILE_BASE_URL", "").rstrip("/")


SETTINGS = Settings()


def require_gpu() -> None:
    """Bot chi chay tren GPU — fail nhanh neu khong co CUDA, khong fallback CPU."""
    import ctranslate2

    if ctranslate2.get_cuda_device_count() == 0:
        raise RuntimeError("Khong thay GPU (CUDA). Bot nay chi chay tren GPU, khong chay CPU.")
    print("GPU: CUDA co san (ctranslate2)")
