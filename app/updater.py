"""Kiểm tra cập nhật phiên bản qua manifest JSON (thuần stdlib).

Module này tải một file manifest JSON nhỏ trên mạng để biết phiên bản mới nhất,
so với phiên bản hiện tại và báo cho UI biết có nên hiện nút "Cập nhật" hay không.

Không thêm dependency: chỉ dùng urllib, json, dataclasses, re.
Mọi lỗi mạng/parse/timeout đều được nuốt và trả về UpdateInfo.error (không raise),
để menu helper không bao giờ bị crash chỉ vì kiểm tra cập nhật thất bại.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

# Nguồn cập nhật: file latest.json đính kèm trong Release mới nhất của repo.
# Link "releases/latest/download/<file>" luôn trỏ tới release mới nhất.
UPDATE_MANIFEST_URL = (
    "https://github.com/tindoantrong/snapzhot_src/releases/latest/download/latest.json"
)

# User-Agent rõ ràng để server nhận diện, tránh bị một số host chặn request "lạ".
_USER_AGENT = "SnagTin-Updater"


_SAFE_UPDATE_HOSTS = {"github.com", "www.github.com"}


def is_safe_update_url(url: str | None) -> bool:
    """Trả True CHỈ KHI url dùng https VÀ host thuộc github.com / www.github.com.

    Mọi trường hợp khác (http, file, javascript, data, host lạ, url rỗng/None,
    không parse được) đều trả False.
    Hàm thuần — không gọi mạng, không side-effect.
    """
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return host in _SAFE_UPDATE_HOSTS


def parse_version(s: str) -> tuple[int, ...]:
    """Bóc các số trong chuỗi version thành tuple int.

    Bỏ tiền tố ``v``/``V`` và mọi ký tự không phải số.
    Ví dụ: ``"v1.2.3"`` -> ``(1, 2, 3)``, ``"0.1.0"`` -> ``(0, 1, 0)``.
    An toàn với phần lẻ (build/pre-release): chỉ lấy các nhóm chữ số.
    Chuỗi không có số nào -> ``(0,)``.
    """
    if not s:
        return (0,)
    s = s.strip()
    if s[:1] in ("v", "V"):
        s = s[1:]
    parts = re.findall(r"\d+", s)
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def is_newer(remote: str, local: str) -> bool:
    """True nếu ``remote`` mới hơn ``local`` (so theo tuple version, pad 0 cho cùng độ dài)."""
    r, l = parse_version(remote), parse_version(local)
    n = max(len(r), len(l))
    r += (0,) * (n - len(r))
    l += (0,) * (n - len(l))
    return r > l


@dataclass
class UpdateInfo:
    available: bool
    current: str
    latest: str
    url: str
    notes: str
    error: str | None = None


def check_for_updates(
    current_version: str,
    manifest_url: str = UPDATE_MANIFEST_URL,
    timeout: float = 8.0,
) -> UpdateInfo:
    """Tải manifest JSON và cho biết có bản mới hơn ``current_version`` không.

    Schema manifest kỳ vọng::

        {"version": "1.2.3", "url": "https://...", "notes": "..."}

    KHÔNG raise: mọi lỗi (mạng, timeout, JSON hỏng, thiếu trường) đều trả về
    ``UpdateInfo(available=False, error="<thông điệp tiếng Việt>")``.
    """
    try:
        req = urllib.request.Request(
            manifest_url, headers={"User-Agent": _USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
    except urllib.error.URLError:
        return UpdateInfo(
            available=False,
            current=current_version,
            latest="",
            url="",
            notes="",
            error="Không kết nối được tới máy chủ cập nhật. Vui lòng kiểm tra mạng.",
        )
    except (ValueError, UnicodeDecodeError):
        return UpdateInfo(
            available=False,
            current=current_version,
            latest="",
            url="",
            notes="",
            error="Dữ liệu cập nhật không hợp lệ.",
        )
    except Exception:
        return UpdateInfo(
            available=False,
            current=current_version,
            latest="",
            url="",
            notes="",
            error="Có lỗi khi kiểm tra cập nhật.",
        )

    if not isinstance(data, dict):
        return UpdateInfo(
            available=False,
            current=current_version,
            latest="",
            url="",
            notes="",
            error="Dữ liệu cập nhật không hợp lệ.",
        )

    latest = str(data.get("version", "")).strip()
    if not latest:
        return UpdateInfo(
            available=False,
            current=current_version,
            latest="",
            url="",
            notes="",
            error="Manifest cập nhật thiếu thông tin phiên bản.",
        )

    url = str(data.get("url", "")).strip()
    notes = str(data.get("notes", "")).strip()

    return UpdateInfo(
        available=is_newer(latest, current_version),
        current=current_version,
        latest=latest,
        url=url,
        notes=notes,
        error=None,
    )
