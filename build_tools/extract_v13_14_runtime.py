from __future__ import annotations

import importlib.util
import shutil
import struct
import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.loader.pyimod01_archive import PYZ_ITEM_MODULE, PYZ_ITEM_PKG, PYZ_ITEM_NSPKG

MAIN_ENTRY = "분석설계V13-14_해지계약출력제외"
APP_FOLDERS = {"assets", "templates", "guides"}


def safe_rel(name: str) -> Path:
    name = name.replace("\\", "/").lstrip("/")
    parts = [p for p in name.split("/") if p not in ("", ".", "..")]
    return Path(*parts)


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main(exe_path: Path, runtime_dir: Path, app_dir: Path) -> None:
    for folder in (runtime_dir, app_dir):
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)

    archive = CArchiveReader(str(exe_path))
    pyc_header = importlib.util.MAGIC_NUMBER + struct.pack("<III", 0, 0, 0)

    # Recover the exact compiled V13-14 main program from the known-good distribution.
    if MAIN_ENTRY not in archive.toc:
        raise RuntimeError(f"V13-14 main entry not found: {MAIN_ENTRY}")
    *_, main_type = archive.toc[MAIN_ENTRY]
    if main_type != "s":
        raise RuntimeError(f"Unexpected main entry type: {main_type!r}")
    main_marshaled_code = archive.extract(MAIN_ENTRY)
    write_file(app_dir / f"{MAIN_ENTRY}.pyc", pyc_header + main_marshaled_code)

    # Recover the original data/native payload. Assets used by the application itself stay at
    # bundle root; everything else becomes the compatibility runtime used by the V13-14 code.
    for name, entry in archive.toc.items():
        *_, typecode = entry
        if typecode in {"o", "s", "m", "M", "z"}:
            continue
        rel = safe_rel(name)
        if not rel.parts:
            continue
        target_root = app_dir if rel.parts[0] in APP_FOLDERS else runtime_dir
        write_file(target_root / rel, archive.extract(name))

    # Recreate every module from V13-14's embedded PYZ as Python 3.12 .pyc files.
    pyz = archive.open_embedded_archive("PYZ.pyz")
    module_count = 0
    for module_name, entry in pyz.toc.items():
        typecode, *_ = entry
        parts = module_name.split(".")
        if typecode == PYZ_ITEM_NSPKG:
            runtime_dir.joinpath(*parts).mkdir(parents=True, exist_ok=True)
            continue
        if typecode not in (PYZ_ITEM_MODULE, PYZ_ITEM_PKG):
            continue
        raw = pyz.extract(module_name, raw=True)
        if raw is None:
            continue
        if typecode == PYZ_ITEM_PKG:
            dest = runtime_dir.joinpath(*parts, "__init__.pyc")
        else:
            dest = runtime_dir.joinpath(*parts).with_suffix(".pyc")
        write_file(dest, pyc_header + raw)
        module_count += 1

    # The new PyInstaller executable supplies these two bootstrap/runtime files itself.
    # Keeping old copies at bundle root can make Windows load the wrong interpreter runtime.
    for duplicate in (runtime_dir / "python312.dll", runtime_dir / "base_library.zip"):
        duplicate.unlink(missing_ok=True)

    print(f"V13-14 main pyc: {app_dir / (MAIN_ENTRY + '.pyc')}")
    print(f"Recovered PYZ modules: {module_count}")
    print(f"Compatibility runtime files: {sum(1 for p in runtime_dir.rglob('*') if p.is_file())}")
    print(f"Application payload files: {sum(1 for p in app_dir.rglob('*') if p.is_file())}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: extract_v13_14_runtime.py <V13-14.exe> <runtime-dir> <app-dir>")
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
