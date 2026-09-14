# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

root = Path(SPECPATH)
app_payload = root / "app_payload"
app_src = root / "app_src"
legacy_runtime = root / "legacy_runtime"

# V13-14 메인 코드는 사용자가 검증한 V13-14 배포 EXE에서 추출한 .pyc를 그대로 사용한다.
datas = [
    (str(app_payload / "분석설계V13-14_해지계약출력제외.pyc"), "."),
    (str(app_src / "분석설계V13-15_관리자원격승인.py"), "."),
    (str(app_src / "분석설계V13-16_RPC오류수정.py"), "."),
    (str(app_src / "분석설계V13-17_신청일시한국시간표시.py"), "."),
    (str(app_src / "분석설계V13-18_원격승인배포보완.py"), "."),
    (str(app_src / "분석설계V13-19_원격승인완성판.py"), "."),
    (str(app_src / "remote_license_v13_15.py"), "."),
    (str(app_src / "remote_license_v13_16.py"), "."),
]

for folder in ("assets", "templates", "guides"):
    folder_path = app_payload / folder
    if folder_path.exists():
        datas.append((str(folder_path), folder))

# V13-14에서 실제로 사용하던 Python 모듈/PYD/DLL/패키지 리소스 전체를 호환 런타임으로 포함한다.
datas.append((str(legacy_runtime), "legacy_runtime"))

a = Analysis(
    [str(root / "src" / "분석설계VB13-1.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="분석설계VB13-1_윈도우단일EXE배포용",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
