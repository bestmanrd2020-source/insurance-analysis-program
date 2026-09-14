from __future__ import annotations

import base64
import marshal
import struct
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_EXE = ROOT / "V13-14-source.exe"
OVERLAY_PARTS = ROOT / "overlay_parts"
OUT = ROOT / "src"
COOKIE_FMT = "!8sIIII64s"
COOKIE_SIZE = struct.calcsize(COOKIE_FMT)
MAGIC = b"MEI\014\013\012\013\016"


def parse_carchive(path: Path):
    blob = path.read_bytes()
    magic, pkglen, tocoff, toclen, pyvers, pylib = struct.unpack(COOKIE_FMT, blob[-COOKIE_SIZE:])
    if magic != MAGIC:
        raise RuntimeError("PyInstaller CArchive cookie not found")
    start = len(blob) - pkglen
    toc = blob[start + tocoff : start + tocoff + toclen]
    entries = {}
    i = 0
    while i < len(toc):
        elen = struct.unpack("!I", toc[i : i + 4])[0]
        body = toc[i + 4 : i + elen]
        pos, clen, ulen = struct.unpack("!III", body[:12])
        compressed = body[12]
        typecode = chr(body[13])
        name = body[14:].split(b"\0", 1)[0].decode("utf-8").replace("\\", "/")
        raw = blob[start + pos : start + pos + clen]
        if compressed:
            raw = zlib.decompress(raw)
        if len(raw) != ulen:
            raise RuntimeError(f"CArchive length mismatch: {name}")
        entries[name] = (typecode, raw)
        i += elen
    return pyvers, entries


def sourceless_pyc(pyc_magic: bytes, marshalled_code: bytes) -> bytes:
    return pyc_magic + b"\0" * 12 + marshalled_code


def main() -> None:
    if not SRC_EXE.exists():
        raise RuntimeError("V13-14-source.exe is missing. The workflow must download the stable V13-14 EXE first.")
    OUT.mkdir(parents=True, exist_ok=True)

    pyvers, entries = parse_carchive(SRC_EXE)
    if pyvers != 312:
        raise RuntimeError(f"Expected Python 3.12 archive, got {pyvers}")

    pyz = entries["PYZ.pyz"][1]
    if pyz[:4] != b"PYZ\0":
        raise RuntimeError("Invalid PYZ archive")
    pyc_magic = pyz[4:8]
    tocpos = struct.unpack("!I", pyz[8:12])[0]
    pyz_toc = dict(marshal.loads(pyz[tocpos:]))

    main_entry = "분석설계V13-14_해지계약출력제외"
    if main_entry not in entries:
        raise RuntimeError("V13-14 main script not found in stable EXE")
    _typecode, main_marshaled = entries[main_entry]
    (OUT / "analysis_v13_14_compiled.pyc").write_bytes(sourceless_pyc(pyc_magic, main_marshaled))

    shim = '''from __future__ import annotations\nimport importlib.util\nimport sys\nfrom pathlib import Path\nHERE = Path(__file__).resolve().parent\nPYC = HERE / "analysis_v13_14_compiled.pyc"\nif getattr(sys, "frozen", False):\n    PYC = Path(getattr(sys, "_MEIPASS", HERE)) / PYC.name\n_spec = importlib.util.spec_from_file_location("_analysis_v13_14_compiled", PYC)\nif _spec is None or _spec.loader is None:\n    raise ImportError("V13-14 compiled base could not be loaded")\n_mod = importlib.util.module_from_spec(_spec)\nsys.modules[_spec.name] = _mod\n_spec.loader.exec_module(_mod)\nfor _key, _value in vars(_mod).items():\n    if _key not in {"__name__", "__loader__", "__package__", "__spec__", "__file__", "__cached__"}:\n        globals()[_key] = _value\n'''
    (OUT / "분석설계V13-14_해지계약출력제외.py").write_text(shim, encoding="utf-8")

    helper_modules = [
        "insurance_pdf_parser_v11_15", "app_observability", "support_center",
        "renewal_writer_engine_v13_3", "consultation_report", "asset_manager",
    ]
    for module in helper_modules:
        if module not in pyz_toc:
            raise RuntimeError(f"Missing helper module in V13-14: {module}")
        _is_pkg, offset, length = pyz_toc[module]
        marshalled_code = zlib.decompress(pyz[offset : offset + length])
        (OUT / f"{module}.pyc").write_bytes(sourceless_pyc(pyc_magic, marshalled_code))
        print("recovered helper", module)

    data_names = [
        "assets/상단_보장분석_배너.png",
        "assets/카카오페이_송금QR_김승혁.png",
        "templates/통합양식.xlsx",
        "templates/갱신형3 5 10 20 30년갱신.xlsx",
        "guides/kb손보 데이터파일 만들기 가이드.pdf",
    ]
    for name in data_names:
        if name not in entries:
            raise RuntimeError(f"Missing resource in V13-14: {name}")
        _typecode, raw = entries[name]
        dest = OUT / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        print("recovered resource", name)

    part_files = sorted(OVERLAY_PARTS.glob("*.txt"))
    if len(part_files) != 5:
        raise RuntimeError(f"Expected 5 overlay chunks, got {len(part_files)}")
    overlay_text = ''.join(''.join(p.read_text(encoding='ascii').split()) for p in part_files)
    overlay_text += '=' * (-len(overlay_text) % 4)
    overlay_bytes = base64.b64decode(overlay_text)
    overlay_zip = ROOT / "overlay.zip"
    overlay_zip.write_bytes(overlay_bytes)
    if not zipfile.is_zipfile(overlay_zip):
        raise RuntimeError(f"Overlay bundle is not a valid ZIP (decoded size={len(overlay_bytes)})")
    with zipfile.ZipFile(overlay_zip, "r") as zf:
        zf.extractall(OUT)
    overlay_zip.unlink(missing_ok=True)

    required = [
        "분석설계V13-15_관리자원격승인.py",
        "분석설계V13-16_RPC오류수정.py",
        "분석설계V13-17_신청일시한국시간표시.py",
        "분석설계V13-18_원격승인배포보완.py",
        "분석설계V13-19_원격승인완성판.py",
        "remote_license_v13_15.pyc",
        "remote_license_v13_16.pyc",
    ]
    for name in required:
        if not (OUT / name).exists():
            raise RuntimeError(f"Overlay file missing: {name}")

    print("VB13-1 build source prepared at", OUT)


if __name__ == "__main__":
    main()
