"""분석설계 V13-16 이용권 RPC 오류 수정판.

V13-15의 모든 기능과 화면을 그대로 사용하고 버전만 독립적으로 올린다.
Supabase의 digest 검색 경로 수정은 V13-16 전용 SQL 마이그레이션으로 적용한다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "분석설계V13-15_관리자원격승인.py"
if getattr(sys, "frozen", False):
    BASE_PATH = Path(getattr(sys, "_MEIPASS", HERE)) / BASE_PATH.name

spec = importlib.util.spec_from_file_location("analysis_v13_15_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("V13-15 기반 프로그램을 불러오지 못했습니다.")
v15 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v15
spec.loader.exec_module(v15)

v15.base.CURRENT_APP_VERSION = "V13-16"
v15.base.APP_TITLE = "분석설계 V13-16"

App = v15.OriginalApp
_v15_init = App.__init__


def _v13_16_init(self):
    _v15_init(self)
    client = getattr(self, "remote_license_client", None)
    if client is not None:
        client.version = "V13-16"


App.__init__ = _v13_16_init


def main() -> int:
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
