# MediaConverter
# Copyright (C) 2026 누구세요
#
# This file is part of MediaConverter.
#
# MediaConverter is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# MediaConverter is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with MediaConverter. If not, see <https://www.gnu.org/licenses/>.

"""
스크립트로 실행(`python main.py`)할 때와 PyInstaller로 만든 .exe로 실행할 때
모두 동일하게 동작하는 경로 헬퍼.

두 가지 종류의 경로를 구분해서 다룬다.

1. resource_path() - main.ui, ICON.ico 처럼 exe 안에 "포함"시키는 리소스.
   PyInstaller onefile로 빌드하면 실행 시 sys._MEIPASS 라는 임시 폴더에
   풀려서 거기서 찾아야 한다.

2. bundled_tool_path() - ffmpeg.exe, ffprobe.exe 처럼 용량이 커서 exe 안에
   넣지 않고 exe "옆" bin 폴더에 같이 배포하는 외부 실행파일. exe가 어디 있든
   (설치 위치) 그 exe와 같은 폴더의 bin/ 에서 찾는다.
"""

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts: str) -> str:
    """exe 안에 번들된(datas로 추가한) 리소스의 경로."""
    base = getattr(sys, "_MEIPASS", _PROJECT_ROOT)
    return os.path.join(base, *parts)


def app_dir() -> str:
    """실행 파일(.exe) 또는 main.py가 위치한 폴더.

    PyInstaller onefile로 얼린 상태에서는 sys.executable이 실제 .exe 경로이고,
    sys._MEIPASS(임시 압축해제 폴더)와는 다르다. ffmpeg.exe처럼 exe 안에 넣지
    않고 "옆"에 두는 파일은 이 폴더 기준으로 찾아야 한다.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return _PROJECT_ROOT


def bundled_tool_path(name: str) -> str:
    """exe와 같은 폴더의 bin/ 안에 동봉된 외부 실행파일(ffmpeg.exe 등) 경로."""
    return os.path.join(app_dir(), "bin", name)
