# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
for package in ('selenium', 'truststore', 'pymupdf', 'openpyxl', 'xlwings', 'xlrd', 'cryptography', 'PIL'):
    hiddenimports += collect_submodules(package)
hiddenimports += [
    'insurance_pdf_parser_v11_15', 'app_observability', 'support_center',
    'renewal_writer_engine_v13_3', 'consultation_report', 'asset_manager',
    'remote_license_v13_15', 'remote_license_v13_16', 'pyautogui', 'pygetwindow'
]

a = Analysis(
    ['분석설계VB13-1_윈도우배포판.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('analysis_v13_14_compiled.pyc', '.'),
        ('분석설계V13-19_원격승인완성판.py', '.'),
        ('분석설계V13-18_원격승인배포보완.py', '.'),
        ('분석설계V13-17_신청일시한국시간표시.py', '.'),
        ('분석설계V13-16_RPC오류수정.py', '.'),
        ('분석설계V13-15_관리자원격승인.py', '.'),
        ('분석설계V13-14_해지계약출력제외.py', '.'),
        ('assets/상단_보장분석_배너.png', 'assets'),
        ('assets/카카오페이_송금QR_김승혁.png', 'assets'),
        ('templates/통합양식.xlsx', 'templates'),
        ('templates/갱신형3 5 10 20 30년갱신.xlsx', 'templates'),
        ('guides/kb손보 데이터파일 만들기 가이드.pdf', 'guides'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PIL.AvifImagePlugin', 'PIL._avif'],
    noarchive=False, optimize=0,
)

def windows_only(entry):
    p = str(entry[0]).replace('\\', '/').lower()
    return not (
        '/selenium/webdriver/common/linux/selenium-manager' in '/' + p
        or '/selenium/webdriver/common/macos/selenium-manager' in '/' + p
        or p.endswith('pil/_avif.cp312-win_amd64.pyd')
    )

a.binaries = [e for e in a.binaries if windows_only(e)]
a.datas = [e for e in a.datas if windows_only(e)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='분석설계VB13-1_윈도우단일EXE배포용',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
