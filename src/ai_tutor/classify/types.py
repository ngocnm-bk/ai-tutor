from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    lop: int
    mon: str
    chuong: str | None
    bai: str | None
    ky_nang: tuple[str, ...]
    source: str
