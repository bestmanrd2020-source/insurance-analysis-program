"""분석설계 V13-17 신청일시 한국시간 표시판.

Supabase에는 UTC 시각을 그대로 보관하고, 이용권 창의 신청일시만 KST로 표시한다.
V13-16의 RPC 수정과 모든 기존 기능은 유지한다.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "분석설계V13-16_RPC오류수정.py"
if getattr(sys, "frozen", False):
    BASE_PATH = Path(getattr(sys, "_MEIPASS", HERE)) / BASE_PATH.name

spec = importlib.util.spec_from_file_location("analysis_v13_16_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("V13-16 기반 프로그램을 불러오지 못했습니다.")
v16 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v16
spec.loader.exec_module(v16)

v16.v15.base.CURRENT_APP_VERSION = "V13-17"
v16.v15.base.APP_TITLE = "분석설계 V13-17"

KST = timezone(timedelta(hours=9), name="KST")
_original_accept_snapshot = v16.v15.RemoteLicenseClient._accept_snapshot


def _format_kst(value: str) -> str:
    """Supabase UTC timestamptz를 상담 화면용 한국시간 문자열로 바꾼다."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return raw.replace("T", " ")[:16]


def _accept_snapshot_kst(self, payload):
    snapshot = _original_accept_snapshot(self, payload)
    snapshot.requested_at = _format_kst(snapshot.requested_at)
    state = self.store.load()
    if snapshot.requested_at:
        state["remote_requested_at"] = snapshot.requested_at
        self.store.save(state)
    return snapshot


v16.v15.RemoteLicenseClient._accept_snapshot = _accept_snapshot_kst
App = v16.App
_v16_init = App.__init__


def _v13_17_init(self):
    _v16_init(self)
    client = getattr(self, "remote_license_client", None)
    if client is not None:
        client.version = "V13-17"


App.__init__ = _v13_17_init


def main() -> int:
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
