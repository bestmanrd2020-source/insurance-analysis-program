from __future__ import annotations

import importlib.util
import os
import shutil
import struct
import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.loader.pyimod01_archive import PYZ_ITEM_MODULE, PYZ_ITEM_PKG, PYZ_ITEM_NSPKG


def safe_rel(name: str) -> Path:
    name = name.replace('\\', '/').lstrip('/')
    parts = [p for p in name.split('/') if p not in ('', '.', '..')]
    return Path(*parts)


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def extract_runtime(exe_path: Path, out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    archive = CArchiveReader(str(exe_path))

    # Keep all payload files from the original, except bootstrap scripts and the embedded PYZ itself.
    # This preserves DLL/PYD files, templates, images, guides, the V13-14~V13-19 source chain,
    # selenium-manager, certificates, Tcl/Tk data, and package resources exactly as in V13-21.
    for name, entry in archive.toc.items():
        *_, typecode = entry
        if typecode in {'o', 's', 'm', 'M', 'z'}:
            continue
        data = archive.extract(name)
        write_file(out_dir / safe_rel(name), data)

    # The source-chain files and assets are stored as CArchive payloads too. Ensure they are present.
    required = [
        '분석설계V13-14_해지계약출력제외.py',
        '분석설계V13-15_관리자원격승인.py',
        '분석설계V13-16_RPC오류수정.py',
        '분석설계V13-17_신청일시한국시간표시.py',
        '분석설계V13-18_원격승인배포보완.py',
        '분석설계V13-19_원격승인완성판.py',
    ]
    for rel in required:
        if not (out_dir / rel).exists():
            # In some PyInstaller builds these are marked as binary-like entries; explicitly recover them.
            if rel in archive.toc:
                write_file(out_dir / rel, archive.extract(rel))
            else:
                raise RuntimeError(f'Missing required embedded file: {rel}')

    # Recreate Python modules from the original PYZ as importable .pyc files.
    pyz = archive.open_embedded_archive('PYZ.pyz')
    pyc_header = importlib.util.MAGIC_NUMBER + struct.pack('<III', 0, 0, 0)
    module_count = 0
    for module_name, entry in pyz.toc.items():
        typecode, *_ = entry
        if typecode == PYZ_ITEM_NSPKG:
            (out_dir / Path(*module_name.split('.'))).mkdir(parents=True, exist_ok=True)
            continue
        if typecode not in (PYZ_ITEM_MODULE, PYZ_ITEM_PKG):
            continue
        raw = pyz.extract(module_name, raw=True)
        if raw is None:
            continue
        rel_parts = module_name.split('.')
        if typecode == PYZ_ITEM_PKG:
            dest = out_dir.joinpath(*rel_parts, '__init__.pyc')
        else:
            dest = out_dir.joinpath(*rel_parts).with_suffix('.pyc')
        write_file(dest, pyc_header + raw)
        module_count += 1

    print(f'Extracted runtime: {out_dir}')
    print(f'PYZ modules written: {module_count}')
    print(f'Total files: {sum(1 for p in out_dir.rglob("*") if p.is_file())}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: extract_runtime.py <source.exe> <output-dir>')
    extract_runtime(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
