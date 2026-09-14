"""분석설계 V13-19 원격 승인 완성판.

V13-18의 승인 응답 호환과 한국시간 표시를 유지하는 독립 배포판이다.
이전 버전 소스와 EXE는 수정하지 않는다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import remote_license_v13_16 as remote_license_v13_15


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "분석설계V13-18_원격승인배포보완.py"
if getattr(sys, "frozen", False):
    BASE_PATH = Path(getattr(sys, "_MEIPASS", HERE)) / BASE_PATH.name

sys.modules["remote_license_v13_15"] = remote_license_v13_15
spec = importlib.util.spec_from_file_location("analysis_v13_18_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("V13-18 기반 프로그램을 불러오지 못했습니다.")
v18 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v18
spec.loader.exec_module(v18)

v18.v17.v16.v15.base.CURRENT_APP_VERSION = "V13-19"
v18.v17.v16.v15.base.APP_TITLE = "분석설계 V13-19"

App = v18.App
_v18_init = App.__init__


def _v13_19_init(self):
    _v18_init(self)
    client = getattr(self, "remote_license_client", None)
    if client is not None:
        client.version = "V13-19"


App.__init__ = _v13_19_init


def main() -> int:
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
