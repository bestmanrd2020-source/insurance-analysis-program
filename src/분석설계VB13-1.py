"""분석설계 VB13-1 - Windows 단일 EXE 배포판.

현재 V13-19 원격승인 기능을 유지하고, V13-14까지 정상 동작했던 표준
PyInstaller 부트로더/자동업데이트 흐름으로 다시 빌드하기 위한 진입점이다.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path


BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)).resolve()
LEGACY_RUNTIME = BUNDLE_ROOT / "legacy_runtime"

# V13-21 배포판에서 검증된 Python 모듈/PYD/DLL을 그대로 재사용한다.
if LEGACY_RUNTIME.exists():
    sys.path.insert(0, str(LEGACY_RUNTIME))
    base_zip = LEGACY_RUNTIME / "base_library.zip"
    if base_zip.exists():
        sys.path.insert(0, str(base_zip))
    try:
        os.add_dll_directory(str(LEGACY_RUNTIME))
    except (AttributeError, FileNotFoundError, OSError):
        pass
    os.environ["PATH"] = str(LEGACY_RUNTIME) + os.pathsep + os.environ.get("PATH", "")

    tcl_dir = LEGACY_RUNTIME / "_tcl_data"
    tk_dir = LEGACY_RUNTIME / "_tk_data"
    if tcl_dir.exists():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
    if tk_dir.exists():
        os.environ.setdefault("TK_LIBRARY", str(tk_dir))

BASE_PATH = BUNDLE_ROOT / "분석설계V13-19_원격승인완성판.py"
if not BASE_PATH.exists():
    raise SystemExit(f"V13-19 기반 프로그램을 찾지 못했습니다: {BASE_PATH}")

spec = importlib.util.spec_from_file_location("analysis_v13_19_vb13_1", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("V13-19 기반 프로그램을 불러오지 못했습니다.")
v19 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v19
spec.loader.exec_module(v19)

base = v19.v18.v17.v16.v15.base
_original_version_number_tuple = base.version_number_tuple


def _vb13_version_number_tuple(value: str) -> tuple[int, ...]:
    """기존 V13-x와 새 VB13-x를 함께 비교한다.

    VB13-1은 기존 배포 계열의 다음 버전인 V13-24와 동일한 순서값으로 본다.
    이후 VB13-2, VB13-3도 연속적으로 비교된다.
    """
    text = str(value or "").strip()
    match = re.search(r"(?i)\bvb\s*(\d+)(?:[._-](\d+))?", text)
    if match:
        major = int(match.group(1) or 0)
        minor = int(match.group(2) or 0)
        if major == 13:
            return (13, 23 + minor)
        return (major, minor)
    return _original_version_number_tuple(value)


base.version_number_tuple = _vb13_version_number_tuple
base.CURRENT_APP_VERSION = "VB13-1"
base.APP_TITLE = "분석설계 VB13-1"

App = v19.App
_original_init = App.__init__


def _vb13_1_init(self):
    _original_init(self)
    client = getattr(self, "remote_license_client", None)
    if client is not None:
        client.version = "VB13-1"


App.__init__ = _vb13_1_init


def main() -> int:
    # GitHub Actions에서 실제 Windows EXE가 최소한 전체 소스/모듈을 정상 로드하는지 확인한다.
    if "--build-smoke-test" in sys.argv:
        return 0
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
