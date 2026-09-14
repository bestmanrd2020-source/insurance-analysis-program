"""분석설계 VB13-1 Windows 정식 빌드판.

현재 V13-19 원격승인 기능 체인을 그대로 사용하면서 PyInstaller는
V13-14 시절과 같은 표준 Windows bootloader로 새로 빌드한다.
V13-21의 커스텀 bootloader는 사용하지 않는다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "분석설계V13-19_원격승인완성판.py"
if getattr(sys, "frozen", False):
    BASE_PATH = Path(getattr(sys, "_MEIPASS", HERE)) / BASE_PATH.name

spec = importlib.util.spec_from_file_location("analysis_v13_19_vb13_1_windows", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("V13-19 기반 프로그램을 불러오지 못했습니다.")
v19 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v19
spec.loader.exec_module(v19)

base = v19.v18.v17.v16.v15.base
base.CURRENT_APP_VERSION = "VB13-1"
base.APP_TITLE = "분석설계 VB13-1"

_original_version_number_tuple = base.version_number_tuple


def _vb13_version_number_tuple(value: str) -> tuple[int, ...]:
    text = str(value or "").strip().upper()
    if text == "VB13-1":
        return (13, 24)
    return _original_version_number_tuple(value)


base.version_number_tuple = _vb13_version_number_tuple

App = v19.App
_original_init = App.__init__


def _vb13_init(self):
    _original_init(self)
    client = getattr(self, "remote_license_client", None)
    if client is not None:
        client.version = "VB13-1"


App.__init__ = _vb13_init


def main() -> int:
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
