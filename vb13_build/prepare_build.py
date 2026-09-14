from __future__ import annotations

import marshal
import struct
import urllib.request
import zlib
from pathlib import Path

RELEASE_EXE_URL = "https://github.com/bestmanrd2020-source/insurance-analysis-program/releases/download/V13-21/V13-21_.EXE._.exe"
ROOT = Path(__file__).resolve().parent
SRC_EXE = ROOT / "V13-21-source.exe"
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
        entries[name] = (typecode, raw)
        i += elen
    return pyvers, entries


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not SRC_EXE.exists():
        print("Downloading V13-21 release EXE...")
        req = urllib.request.Request(RELEASE_EXE_URL, headers={"User-Agent": "VB13-1-Windows-Builder"})
        with urllib.request.urlopen(req, timeout=120) as response, SRC_EXE.open("wb") as fh:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)

    pyvers, entries = parse_carchive(SRC_EXE)
    if pyvers != 312:
        raise RuntimeError(f"Expected Python 3.12 archive, got {pyvers}")

    data_names = [
        "분석설계V13-14_해지계약출력제외.py",
        "분석설계V13-15_관리자원격승인.py",
        "분석설계V13-16_RPC오류수정.py",
        "분석설계V13-17_신청일시한국시간표시.py",
        "분석설계V13-18_원격승인배포보완.py",
        "분석설계V13-19_원격승인완성판.py",
        "assets/상단_보장분석_배너.png",
        "assets/카카오페이_송금QR_김승혁.png",
        "templates/통합양식.xlsx",
        "templates/갱신형3 5 10 20 30년갱신.xlsx",
        "guides/kb손보 데이터파일 만들기 가이드.pdf",
    ]
    for name in data_names:
        _typecode, raw = entries[name]
        dest = OUT / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        print("extracted", name, len(raw))

    pyz = entries["PYZ.pyz"][1]
    if pyz[:4] != b"PYZ\0":
        raise RuntimeError("Invalid PYZ archive")
    pyc_magic = pyz[4:8]
    tocpos = struct.unpack("!I", pyz[8:12])[0]
    pyz_toc = dict(marshal.loads(pyz[tocpos:]))

    custom_modules = [
        "insurance_pdf_parser_v11_15",
        "app_observability",
        "support_center",
        "renewal_writer_engine_v13_3",
        "consultation_report",
        "asset_manager",
        "remote_license_v13_15",
        "remote_license_v13_16",
    ]
    for module in custom_modules:
        _is_pkg, offset, length = pyz_toc[module]
        marshalled_code = zlib.decompress(pyz[offset : offset + length])
        # Sourceless Python 3.12 pyc: magic + 12-byte zero header + marshalled code.
        (OUT / f"{module}.pyc").write_bytes(pyc_magic + b"\0" * 12 + marshalled_code)
        print("pyc", module, len(marshalled_code))

    print("Build source prepared at", OUT)


if __name__ == "__main__":
    main()
