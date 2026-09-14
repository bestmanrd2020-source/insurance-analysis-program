"""V13-16 원격 이용권 응답 호환 보완.

Supabase 응답 컬럼이 signed_license_code로 내려오는 경우에도 기존
license_code 필드로 정규화하여 V13-15 검증 흐름을 그대로 사용한다.
"""
from __future__ import annotations

from typing import Any

from remote_license_v13_15 import *  # noqa: F401,F403
from remote_license_v13_15 import RemoteSnapshot


_v13_15_from_payload = RemoteSnapshot.from_payload.__func__


def _from_payload_v13_16(cls, payload: Any):
    """서버 컬럼명 변경에도 승인코드를 빠뜨리지 않고 읽는다."""
    normalized = payload
    if isinstance(payload, list):
        normalized = [dict(item) if isinstance(item, dict) else item for item in payload]
        for item in normalized:
            if isinstance(item, dict) and not item.get("license_code"):
                item["license_code"] = item.get("signed_license_code", "")
    elif isinstance(payload, dict):
        normalized = dict(payload)
        if not normalized.get("license_code"):
            normalized["license_code"] = normalized.get("signed_license_code", "")
    return _v13_15_from_payload(cls, normalized)


RemoteSnapshot.from_payload = classmethod(_from_payload_v13_16)
