"""분석설계 V13-18 원격 승인 배포 보완판.

V13-17의 KST 표시를 유지하면서, 승인 서버의 signed_license_code 응답을
프로그램 승인코드로 확실히 반영한다. 이전 버전 파일은 보존한다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import remote_license_v13_16 as remote_license_v13_15


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "분석설계V13-17_신청일시한국시간표시.py"
if getattr(sys, "frozen", False):
    BASE_PATH = Path(getattr(sys, "_MEIPASS", HERE)) / BASE_PATH.name

sys.modules["remote_license_v13_15"] = remote_license_v13_15
spec = importlib.util.spec_from_file_location("analysis_v13_17_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("V13-17 기반 프로그램을 불러오지 못했습니다.")
v17 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v17
spec.loader.exec_module(v17)

v17.v16.v15.base.CURRENT_APP_VERSION = "V13-18"
v17.v16.v15.base.APP_TITLE = "분석설계 V13-18"

App = v17.App
_v17_init = App.__init__


def _v13_18_init(self):
    _v17_init(self)
    client = getattr(self, "remote_license_client", None)
    if client is not None:
        client.version = "V13-18"


App.__init__ = _v13_18_init


def main() -> int:
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
