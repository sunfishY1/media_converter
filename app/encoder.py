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
ffmpeg 실행 파일을 subprocess로 직접 호출하는 인코더 모듈.

venv 에 설치된 'ffmpeg' 파이썬 패키지(PyPI: ffmpeg 1.4)는 옛날식 문자열 커맨드
래퍼라 경로에 공백/특수문자가 있으면 깨지기 쉽고, AMV 같은 특수 코덱 옵션을
유연하게 넘기기도 어렵다. 그래서 여기서는 그 패키지를 사용하지 않고, ffmpeg.exe
를 리스트 형태 인자로 직접 호출한다.

ffmpeg/ffprobe 실행파일은 두 군데에서 찾는다 (우선순위 순).
  1. exe(또는 main.py)와 같은 폴더의 bin\\ffmpeg.exe, bin\\ffprobe.exe
     (배포용으로 동봉한 것. app/paths.bundled_tool_path 참고)
  2. 시스템 PATH
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

from . import formats
from .paths import bundled_tool_path

_TIME_RE = re.compile(r"out_time_ms=(\d+)")
_PROGRESS_DONE_RE = re.compile(r"progress=(end|continue)")

ProgressCallback = Callable[[Optional[float], str], None]


class EncodeCancelled(Exception):
    """사용자가 변환을 취소했을 때 발생시키는 예외"""


class FfmpegNotFound(RuntimeError):
    pass


def _find_tool(name: str) -> Optional[str]:
    """bin/ 에 동봉된 실행파일을 우선 쓰고, 없으면 시스템 PATH에서 찾는다."""
    bundled = bundled_tool_path(name + ".exe")
    if os.path.isfile(bundled):
        return bundled
    return shutil.which(name)


def ensure_ffmpeg_available() -> str:
    path = _find_tool("ffmpeg")
    if not path:
        raise FfmpegNotFound(
            "ffmpeg 실행 파일을 찾을 수 없습니다. "
            f"'{bundled_tool_path('ffmpeg.exe')}' 에 두거나, "
            "시스템 PATH에 ffmpeg를 등록해 주세요."
        )
    return path


def probe_duration(path: str) -> Optional[float]:
    """ffprobe로 로컬 파일의 길이(초)를 알아낸다. 실패하면 None을 반환한다.

    (로컬 파일 변환 시 진행률 계산에 사용. yt-dlp 다운로드의 경우는
    downloader.DownloadResult.duration 을 그대로 쓰면 되므로 여기서는
    호출하지 않는다.)
    """
    ffprobe_path = _find_tool("ffprobe")
    if not ffprobe_path:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return float(result.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


@dataclass
class EncodeResult:
    output_path: str


def encode(
    input_path: str,
    output_path: str,
    ext: str,
    quality: str,
    duration_hint: Optional[float] = None,
    progress_callback: Optional[ProgressCallback] = None,
    cancel_event=None,
) -> EncodeResult:
    """
    input_path: 다운로드된 원본 파일 경로
    output_path: 최종 결과 파일 경로 (확장자 포함)
    ext: 목표 확장자 (formats.ALL_FORMATS 중 하나)
    quality: mediaComboBox 에서 선택된 품질 라벨
    duration_hint: 초 단위 원본 길이 (yt-dlp info 의 duration). 알 수 없으면 None.
    progress_callback: (percent 0~100 또는 None(진행률 알 수 없음), 상태문구)
    cancel_event: threading.Event 등 .is_set() 지원 객체
    """

    ffmpeg_path = ensure_ffmpeg_available()
    codec_args = formats.build_ffmpeg_args(ext, quality)

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", input_path,
        *codec_args,
        "-progress", "pipe:1",
        "-nostats",
        "-threads", "0",
        output_path,
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    duration_ms = duration_hint * 1000 if duration_hint else None
    stderr_tail: list[str] = []

    try:
        assert process.stdout is not None
        for line in process.stdout:
            stderr_tail.append(line)
            if len(stderr_tail) > 40:
                stderr_tail.pop(0)

            if cancel_event is not None and cancel_event.is_set():
                process.kill()
                raise EncodeCancelled("변환이 취소되었습니다.")

            if progress_callback is None:
                continue

            time_match = _TIME_RE.search(line)
            if time_match:
                current_ms = int(time_match.group(1))
                if duration_ms:
                    percent = max(0.0, min(100.0, current_ms / duration_ms * 100.0))
                    progress_callback(percent, "변환 중...")
                else:
                    progress_callback(None, "변환 중...")
                continue

            if _PROGRESS_DONE_RE.search(line):
                if "end" in line:
                    progress_callback(100.0, "변환 완료")
    finally:
        process.wait()

    if process.returncode != 0:
        tail = "".join(stderr_tail[-15:])
        raise RuntimeError(f"ffmpeg 변환 실패 (코드 {process.returncode})\n{tail}")

    return EncodeResult(output_path=output_path)
