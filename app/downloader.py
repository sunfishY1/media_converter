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
yt-dlp를 이용해 영상 또는 재생목록의 오디오/비디오를 임시 폴더에 내려받는 모듈.

실제 포맷 변환(코덱/컨테이너 변경)은 담당하지 않는다. 여기서는 최대한 원본에
가까운 품질로 내려받기만 하고, 이후 encoder.py 가 ffmpeg로 최종 변환한다.
"""

from __future__ import annotations

import glob
import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

import yt_dlp

from . import encoder

# 유튜브가 클라이언트별로 요구하는 서명/토큰(PO Token) 정책이 자주 바뀌면서,
# 기본(web) 클라이언트만 쓰면 스트리밍 URL이 403 Forbidden으로 막히는 경우가
# 잦아졌다. 여러 클라이언트를 함께 시도하도록 하면 그중 토큰이 필요 없거나
# 아직 막히지 않은 클라이언트의 포맷을 골라 쓸 수 있어 403을 크게 줄일 수 있다.
_PLAYER_CLIENTS = ["android", "tv", "ios", "web"]

# 일시적인 403/네트워크 오류는 몇 초 후 재시도하면 성공하는 경우가 많다
# (유튜브 쪽 순간적인 봇 탐지/속도제한으로 추정).
_MAX_ATTEMPTS = 3
_RETRY_DELAY_SEC = 5


def _ffmpeg_location() -> Optional[str]:
    """yt-dlp가 내부적으로 쓸 ffmpeg 경로.

    bin/ 에 동봉된 복사본이 있으면 그걸 쓰도록 해서, 비디오+오디오 병합
    같은 yt-dlp 내부 후처리도 시스템 PATH와 무관하게 동작하게 한다.
    없으면 None을 반환해 yt-dlp가 기본 동작(PATH 탐색)을 하도록 둔다.
    """
    try:
        ffmpeg_path = encoder.ensure_ffmpeg_available()
    except encoder.FfmpegNotFound:
        return None
    return os.path.dirname(ffmpeg_path)


class DownloadCancelled(Exception):
    """사용자가 다운로드를 취소했을 때 발생시키는 예외"""


@dataclass
class DownloadResult:
    filepath: str
    title: str
    duration: Optional[float]  # 초 단위, 알 수 없으면 None


@dataclass
class PreviewResult:
    title: str
    additional_count: int


# progress_callback(percent: float, status_text: str) 형태로 호출된다.
ProgressCallback = Callable[[float, str], None]


def get_preview(url: str) -> PreviewResult:
    """Fetch the first title and the remaining item count without downloading media."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "extract_flat": True,
        "extractor_args": {"youtube": {"player_client": _PLAYER_CLIENTS}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries")
    if entries is not None:
        entries = [entry for entry in entries if entry]
        if not entries:
            raise RuntimeError("미리보기에 표시할 영상을 찾지 못했습니다.")
        title = entries[0].get("title") or entries[0].get("id") or "제목 없음"
        count = info.get("playlist_count") or len(entries)
        return PreviewResult(title=title, additional_count=max(0, count - 1))

    title = info.get("title") or info.get("id") or "제목 없음"
    return PreviewResult(title=title, additional_count=0)


def _cleanup_leftovers(tmp_dir: str) -> None:
    """이전 실행에서 남은 임시 파일 제거 (예외적인 잔여 파일 방지)"""
    for path in glob.glob(os.path.join(tmp_dir, "*")):
        try:
            os.remove(path)
        except OSError:
            pass


def download(
    url: str,
    want_video: bool,
    tmp_dir: str,
    progress_callback: Optional[ProgressCallback] = None,
    cancel_event=None,
) -> list[DownloadResult]:
    """
    url: 유튜브 영상 URL
    want_video: True 이면 비디오+오디오, False 이면 오디오만 내려받는다.
    tmp_dir: 다운로드에 사용할 임시 폴더 (호출자가 미리 생성해야 함)
    progress_callback: (percent 0~100, 상태 문자열) 을 전달받는 콜백
    cancel_event: threading.Event 등 .is_set() 을 지원하는 객체. set 되면 취소.
    """

    os.makedirs(tmp_dir, exist_ok=True)
    _cleanup_leftovers(tmp_dir)

    def hook(d: dict) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelled("다운로드가 취소되었습니다.")

        if progress_callback is None:
            return

        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            if total:
                item_percent = downloaded / total * 100.0
            else:
                item_percent = 0.0
            item_info = d.get("info_dict") or {}
            item_index = item_info.get("playlist_index") or 1
            item_count = item_info.get("playlist_count") or 1
            percent = ((item_index - 1) + item_percent / 100.0) / item_count * 100.0
            progress_callback(percent, "다운로드 중...")
        elif status == "finished":
            item_info = d.get("info_dict") or {}
            item_index = item_info.get("playlist_index") or 1
            item_count = item_info.get("playlist_count") or 1
            percent = item_index / item_count * 100.0
            progress_callback(percent, "다운로드 완료, 병합/후처리 중...")

    if want_video:
        fmt = "bestvideo+bestaudio/best"
        merge_output_format = "mkv"
    else:
        fmt = "bestaudio/best"
        merge_output_format = None

    ydl_opts = {
        "format": fmt,
        "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "restrictfilenames": True,
        # 403 대응: 여러 클라이언트를 시도해서 막히지 않은 포맷을 사용
        "extractor_args": {"youtube": {"player_client": _PLAYER_CLIENTS}},
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 3,
        "file_access_retries": 5,
    }
    if merge_output_format:
        ydl_opts["merge_output_format"] = merge_output_format

    ffmpeg_location = _ffmpeg_location()
    if ffmpeg_location:
        ydl_opts["ffmpeg_location"] = ffmpeg_location

    info = None
    last_error: Optional[Exception] = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelled("다운로드가 취소되었습니다.")

        _cleanup_leftovers(tmp_dir)  # 이전 시도의 부분 다운로드 파일 정리
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
            last_error = None
            break
        except DownloadCancelled:
            raise
        except yt_dlp.utils.DownloadError as exc:
            last_error = exc
            if attempt < _MAX_ATTEMPTS:
                if progress_callback is not None:
                    progress_callback(
                        0.0,
                        f"다운로드 실패, {_RETRY_DELAY_SEC}초 후 재시도합니다 "
                        f"({attempt}/{_MAX_ATTEMPTS})...",
                    )
                time.sleep(_RETRY_DELAY_SEC)

    if last_error is not None:
        raise RuntimeError(
            f"유튜브 다운로드 실패 ({_MAX_ATTEMPTS}번 시도함): {last_error}\n"
            "유튜브가 요청을 일시적으로 차단(403)했을 가능성이 있습니다. "
            "잠시 후 다시 시도하거나 yt-dlp를 최신 버전으로 업데이트해 보세요 "
            "(.venv 활성화 후 `pip install -U yt-dlp`)."
        ) from last_error

    if info is None:
        raise RuntimeError("유튜브 정보를 가져오지 못했습니다.")

    entries = info.get("entries")
    if entries is not None:
        entries = [entry for entry in entries if entry]
    else:
        entries = [info]
    if not entries:
        raise RuntimeError("다운로드할 영상을 찾지 못했습니다.")

    results: list[DownloadResult] = []
    for entry in entries:
        video_id = entry.get("id")
        filepath = None
        requested = entry.get("requested_downloads") or []
        for requested_file in requested:
            candidate = requested_file.get("filepath")
            if candidate and os.path.isfile(candidate):
                filepath = candidate
                break

        if filepath is None:
            candidate = entry.get("filepath") or entry.get("_filename")
            if candidate and os.path.isfile(candidate):
                filepath = candidate

        if filepath is None and video_id:
            candidates = [
                path for path in glob.glob(os.path.join(tmp_dir, f"{video_id}.*"))
                if os.path.splitext(path)[1].lower() not in (".part", ".ytdl", ".tmp")
            ]
            if candidates:
                filepath = max(candidates, key=os.path.getmtime)

        if filepath is None:
            continue
        title = entry.get("title") or video_id or "output"
        results.append(DownloadResult(filepath, title, entry.get("duration")))

    if not results:
        raise RuntimeError("다운로드된 영상을 찾지 못했습니다.")
    return results
