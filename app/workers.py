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
다운로드(또는 로컬 파일 읽기) + 변환을 UI 스레드를 막지 않고 수행하는 QThread 워커.

mode="url"  : source는 유튜브 URL. yt-dlp로 내려받은 뒤 ffmpeg로 변환.
mode="file" : source는 로컬 파일 경로. 다운로드 없이 바로 ffmpeg로 변환.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from . import downloader, encoder, formats


class PreviewWorker(QThread):
    """Fetch preview metadata without blocking the interface."""

    preview_ready = pyqtSignal(str, int)
    preview_failed = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self) -> None:
        try:
            preview = downloader.get_preview(self.url)
            self.preview_ready.emit(preview.title, preview.additional_count)
        except Exception as exc:  # noqa: BLE001 - report extractor errors in the UI
            self.preview_failed.emit(str(exc))


def sanitize_filename(name: str) -> str:
    """윈도우 파일명에 쓸 수 없는 문자를 제거/치환"""
    name = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return name or "output"


class ConversionWorker(QThread):
    # percent: 0~100 (int). -1 이면 진행률을 알 수 없음(대기 표시만).
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    # 로그 패널(LogPlaneTextBox)에 표시할 메세지. Logger.info / Logger.error 로 연결.
    log_info = pyqtSignal(str)
    log_error = pyqtSignal(str)
    # success, message_or_output_path
    finished_ok = pyqtSignal(str)
    finished_error = pyqtSignal(str)

    def __init__(self, mode: str, source: str, ext: str, quality: str,
                 output_dir: str, parent=None):
        super().__init__(parent)
        if mode not in ("url", "file"):
            raise ValueError(f"알 수 없는 모드입니다: {mode}")
        self.mode = mode
        self.source = source
        self.ext = ext
        self.quality = quality
        self.output_dir = output_dir
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    # ------------------------------------------------------------------
    # 진행률 콜백
    # ------------------------------------------------------------------
    def _on_download_progress(self, percent: float, status_text: str) -> None:
        # 다운로드는 전체 진행률의 0~50% 구간 (URL 모드에서만 사용)
        self.status_changed.emit(status_text)
        self.progress_changed.emit(int(percent * 0.5))

    def _on_encode_progress_url_mode(self, percent, status_text: str) -> None:
        self.status_changed.emit(status_text)
        if percent is None:
            self.progress_changed.emit(-1)
        else:
            self.progress_changed.emit(50 + int(percent * 0.5))

    def _on_encode_progress_file_mode(self, percent, status_text: str) -> None:
        # 파일 모드는 다운로드 단계가 없으므로 0~100% 전체를 인코딩에 사용
        self.status_changed.emit(status_text)
        if percent is None:
            self.progress_changed.emit(-1)
        else:
            self.progress_changed.emit(int(percent))

    # ------------------------------------------------------------------
    # 실행
    # ------------------------------------------------------------------
    def run(self) -> None:
        if self.mode == "url":
            self.log_info.emit(f"변환 시작 (URL): {self.source}")
        else:
            self.log_info.emit(f"변환 시작 (파일): {self.source}")

        if self.mode == "url":
            self._run_url_mode()
        else:
            self._run_file_mode()

    def _run_url_mode(self) -> None:
        tmp_dir = tempfile.mkdtemp(prefix="mp3_converter_")
        try:
            want_video = not formats.is_audio_format(self.ext)

            self.status_changed.emit("영상 정보를 확인하고 다운로드하는 중...")
            results = downloader.download(
                self.source,
                want_video=want_video,
                tmp_dir=tmp_dir,
                progress_callback=self._on_download_progress,
                cancel_event=self._cancel_event,
            )

            os.makedirs(self.output_dir, exist_ok=True)
            output_paths = []
            total = len(results)
            for index, result in enumerate(results, start=1):
                if self._cancel_event.is_set():
                    raise encoder.EncodeCancelled("변환이 취소되었습니다.")

                out_name = sanitize_filename(result.title) + f".{self.ext}"
                output_path = os.path.join(self.output_dir, out_name)
                suffix = 1
                while os.path.exists(output_path):
                    suffix += 1
                    out_name = f"{sanitize_filename(result.title)} ({index}).{self.ext}"
                    if suffix > 2:
                        out_name = (
                            f"{sanitize_filename(result.title)} ({index}-{suffix - 1}).{self.ext}"
                        )
                    output_path = os.path.join(self.output_dir, out_name)

                self.status_changed.emit(
                    f"영상 변환 중... ({index}/{total})"
                )

                def encode_progress(percent, status, item_index=index):
                    self.status_changed.emit(f"{status} ({item_index}/{total})")
                    if percent is None:
                        self.progress_changed.emit(-1)
                    else:
                        overall = ((item_index - 1) + percent / 100.0) / total
                        self.progress_changed.emit(50 + int(overall * 50))

                encoder.encode(
                    input_path=result.filepath,
                    output_path=output_path,
                    ext=self.ext,
                    quality=self.quality,
                    duration_hint=result.duration,
                    progress_callback=encode_progress,
                    cancel_event=self._cancel_event,
                )
                output_paths.append(output_path)

            self._emit_success(output_paths)

        except (downloader.DownloadCancelled, encoder.EncodeCancelled):
            self._emit_cancelled()
        except Exception as exc:  # noqa: BLE001 - UI에 그대로 메시지 전달
            self._emit_failure(exc)
        finally:
            self._cleanup(tmp_dir)

    def _run_file_mode(self) -> None:
        try:
            if not os.path.isfile(self.source):
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {self.source}")

            os.makedirs(self.output_dir, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(self.source))[0]
            out_name = sanitize_filename(base_name) + f".{self.ext}"
            output_path = os.path.join(self.output_dir, out_name)

            duration = encoder.probe_duration(self.source)

            self.status_changed.emit(f"{self.ext.upper()} 형식으로 변환하는 중...")
            encoder.encode(
                input_path=self.source,
                output_path=output_path,
                ext=self.ext,
                quality=self.quality,
                duration_hint=duration,
                progress_callback=self._on_encode_progress_file_mode,
                cancel_event=self._cancel_event,
            )

            self._emit_success(output_path)

        except encoder.EncodeCancelled:
            self._emit_cancelled()
        except Exception as exc:  # noqa: BLE001 - UI에 그대로 메시지 전달
            self._emit_failure(exc)

    # ------------------------------------------------------------------
    # 결과 처리 공통 로직
    # ------------------------------------------------------------------
    def _emit_success(self, output_paths: list[str] | str) -> None:
        if isinstance(output_paths, str):
            output_paths = [output_paths]
        output_summary = "\n".join(output_paths)
        self.progress_changed.emit(100)
        self.status_changed.emit("완료")
        self.log_info.emit(f"변환 완료: {output_summary}")
        self.finished_ok.emit(output_summary)

    def _emit_cancelled(self) -> None:
        self.status_changed.emit("취소됨")
        self.log_error.emit("변환 취소됨: 사용자가 작업을 취소했습니다.")
        self.finished_error.emit("사용자가 작업을 취소했습니다.")

    def _emit_failure(self, exc: Exception) -> None:
        self.status_changed.emit("오류 발생")
        self.log_error.emit(f"변환 실패: {exc}")
        self.finished_error.emit(str(exc))

    @staticmethod
    def _cleanup(tmp_dir: str) -> None:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
