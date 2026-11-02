# -*- mode: python ; coding: utf-8 -*-
#
# MediaConverter 빌드용 PyInstaller spec 파일.
#
# 사용법 (.venv-win 활성화된 상태, 또는 build.bat 이용):
#   pyinstaller MediaConverter.spec --noconfirm
#
# 결과물: dist\MediaConverter.exe (단일 파일, onefile)
#
# ffmpeg 통합(배포) 방식:
# - ffmpeg.exe / ffprobe.exe는 이 exe 안에 "포함"시키지 않고, exe와 같은
#   폴더의 bin\ 서브폴더에 나란히 둔다 (용량이 커서 onefile에 넣지 않음).
#   app/paths.py의 bundled_tool_path()가 실행 시 이 bin\ 폴더를 먼저 찾고,
#   없으면 시스템 PATH로 대체(fallback)한다.
# - 따라서 배포 시 dist\ 폴더를 통째로 (MediaConverter.exe + bin\ffmpeg.exe +
#   bin\ffprobe.exe) 묶어서 전달해야 한다. build.bat이 빌드 후 프로젝트의
#   bin\ 폴더를 dist\bin\ 으로 자동 복사해준다.
# - PyQt6만 쓰므로 같은 가상환경에 함께 설치된 PySide6/shiboken6은 빌드에서
#   제외해서 용량을 줄인다.
# - main.ui / ICON.ico 는 코드가 아니라 리소스라서 datas에 직접 등록해야
#   exe 안에 포함된다. (app/paths.py의 resource_path() 가 실행 시
#   이 파일들을 올바르게 찾아준다.)

from PyInstaller.utils.hooks import collect_submodules

hidden_imports = collect_submodules("yt_dlp")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("main.ui", "."),
        ("ICON.ico", "."),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "shiboken6"],
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
    name="MediaConverter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # 처음 빌드해서 테스트할 때는 console=True로 바꾸면 에러가 콘솔에 그대로
    # 보여서 디버깅하기 쉽다. 잘 되는 걸 확인한 뒤 배포용으로 False로.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="ICON.ico",
)
