"""Cookie yt-dlp (Netscape format) — upload qua Discord, luu tren VPS, khong in ra chat.
File cookie chua phien dang nhap YouTube/Facebook nen phai coi nhu mat khau:
chi luu o cookies/cookies.txt, chmod 0600, khong bao gio gui lai, khong log gia tri.
"""
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .config import SETTINGS

MAX_BYTES = 1_000_000


@dataclass
class CookieInfo:
    total: int = 0
    valid: int = 0
    expired: int = 0
    domains: set = None

    def __post_init__(self):
        if self.domains is None:
            self.domains = set()


def parse(text: str) -> CookieInfo:
    info = CookieInfo()
    now = int(time.time())
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        info.total += 1
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, expires = parts[0].lstrip("."), parts[4]
        try:
            exp = int(expires)
        except ValueError:
            continue
        if exp != 0 and exp < now:
            info.expired += 1
            continue
        info.valid += 1
        info.domains.add(domain)
    return info


def save(text: str) -> CookieInfo:
    """Kiem tra roi luu de (ghi file tam + doi ten). Tra ve thong ke, khong tra gia tri cookie."""
    info = parse(text)
    if info.valid == 0:
        raise ValueError("File khong co cookie nao con han — xuat lai cookies.txt bang extension 'Get cookies.txt LOCALLY' khi dang dang nhap YouTube/Facebook.")
    path = SETTINGS.cookies_file
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return info


def status() -> CookieInfo | None:
    path = SETTINGS.cookies_file
    if not path.exists():
        return None
    return parse(path.read_text(encoding="utf-8", errors="ignore"))


def clear() -> bool:
    path = SETTINGS.cookies_file
    if path.exists():
        path.unlink()
        return True
    return False
