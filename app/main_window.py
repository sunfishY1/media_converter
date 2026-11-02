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
main.ui (Qt Designer로 제작) 를 로드하여 동작을 연결하는 메인 윈도우.

URL 입력과 로컬 파일 선택 두 가지 소스를 모두 지원한다.
- URLRadioButton 선택 시: stackedWidget이 URLPage를 보여주고, 유튜브 URL을
  yt-dlp로 내려받은 뒤 ffmpeg로 변환한다.
- FileRadioButton 선택 시: stackedWidget이 FilePage를 보여주고, 로컬 파일을
  다운로드 없이 바로 ffmpeg로 변환한다.

변환 진행 상황은 상태표시줄(statusbar)에, 주요 로그(시작/완료/실패)는
LogPlaneTextBox에 타임스탬프 + 색상과 함께 표시한다 (Logger 참고).
"""

from __future__ import annotations

import os
import subprocess
import sys

from PyQt6 import uic
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QFileDialog, QMainWindow, QMessageBox

from . import formats
from .logger import Logger
from .paths import resource_path
from .workers import ConversionWorker, PreviewWorker

# main.ui / ICON.ico 경로. `python main.py`로 직접 실행할 때는 프로젝트 루트
# 기준으로, PyInstaller로 만든 .exe로 실행할 때는 그 안에 번들된 임시 폴더
# (sys._MEIPASS) 기준으로 찾는다 (app/paths.py 참고).
# .spec 파일에서 main.ui / ICON.ico 를 datas로 넣어둬야 한다.
_UI_PATH = resource_path("main.ui")
_ICON_PATH = resource_path("ICON.ico")

# 로컬 파일 선택 시 보여줄 확장자 필터 (미디어 파일 위주)
_FILE_DIALOG_FILTER = (
    "미디어 파일 (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.mp3 *.m4a *.wav *.flac *.aac);;"
    "모든 파일 (*.*)"
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(_UI_PATH, self)

        # main.ui 안의 windowIcon은 상대경로("ICON.ico")라서 실행 위치(cwd)에
        # 따라 못 찾을 수 있다 (특히 PyInstaller onefile .exe). 직접 절대경로로
        # 다시 설정해서 어디서 실행해도 아이콘이 뜨도록 한다.
        if os.path.isfile(_ICON_PATH):
            self.setWindowIcon(QIcon(_ICON_PATH))

        self._worker: ConversionWorker | None = None
        self._preview_worker: PreviewWorker | None = None
        self.logger = Logger(self.LogPlaneTextBox)

        self._setup_format_combo()
        self._setup_default_output_path()
        self._setup_source_selector()

        self.formatComboBox.currentTextChanged.connect(self._on_format_changed)
        self.pathselectButton.clicked.connect(self._on_select_path)
        self.FilePathButton.clicked.connect(self._on_select_file)
        self.convertButton.clicked.connect(self._on_convert_clicked)
        self.previewButton.clicked.connect(self._on_preview_clicked)

        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.setFixedSize(self.size())

    # ------------------------------------------------------------------
    # 초기 설정
    # ------------------------------------------------------------------
    def _setup_format_combo(self) -> None:
        self.formatComboBox.clear()
        for ext in formats.AUDIO_FORMATS:
            self.formatComboBox.addItem(ext.upper(), userData=ext)
        self.formatComboBox.insertSeparator(len(formats.AUDIO_FORMATS))
        for ext in formats.VIDEO_FORMATS:
            self.formatComboBox.addItem(ext.upper(), userData=ext)

        self.formatComboBox.setCurrentIndex(0)
        self._on_format_changed(self.formatComboBox.currentText())

    def _setup_default_output_path(self) -> None:
        if not self.OutputTextB.text().strip():
            default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            self.OutputTextB.setText(default_dir)

    def _setup_source_selector(self) -> None:
        # 같은 부모(widget) 아래 라디오버튼들은 기본적으로 auto-exclusive 라
        # 하나를 선택하면 나머지는 자동으로 해제된다. 시작 화면은 URL 입력으로.
        self.URLRadioButton.setChecked(True)
        self.stackedWidget.setCurrentWidget(self.URLPage)

        self.URLRadioButton.toggled.connect(self._on_source_toggled)
        self.FileRadioButton.toggled.connect(self._on_source_toggled)

    def _current_ext(self) -> str:
        data = self.formatComboBox.currentData()
        if data:
            return data
        return self.formatComboBox.currentText().strip().lower()

    def _is_file_mode(self) -> bool:
        return self.FileRadioButton.isChecked()

    # ------------------------------------------------------------------
    # 이벤트 핸들러
    # ------------------------------------------------------------------
    def _on_format_changed(self, _text: str) -> None:
        ext = self._current_ext()
        if not ext:
            return
        self.mediaComboBox.clear()
        for quality in formats.QUALITY_OPTIONS.get(ext, []):
            self.mediaComboBox.addItem(quality)

    def _on_source_toggled(self, _checked: bool) -> None:
        if self._is_file_mode():
            self.stackedWidget.setCurrentWidget(self.FilePage)
        else:
            self.stackedWidget.setCurrentWidget(self.URLPage)

    def _on_select_path(self) -> None:
        start_dir = self.OutputTextB.text().strip() or os.path.expanduser("~")
        selected = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", start_dir)
        if selected:
            self.OutputTextB.setText(selected)

    def _on_select_file(self) -> None:
        start_dir = os.path.dirname(self.FilePathTextBox.text().strip()) or os.path.expanduser("~")
        selected, _filter = QFileDialog.getOpenFileName(
            self, "변환할 파일 선택", start_dir, _FILE_DIALOG_FILTER
        )
        if selected:
            self.FilePathTextBox.setText(selected)

    def _on_preview_clicked(self) -> None:
        url = self.URLtextB.text().strip()
        if not url:
            QMessageBox.warning(self, "입력 필요", "유튜브 URL을 입력해 주세요.")
            return
        if self._preview_worker is not None and self._preview_worker.isRunning():
            return

        self.previewText.setText("영상 정보를 확인하는 중...")
        self.previewButton.setEnabled(False)
        self._preview_worker = PreviewWorker(url, self)
        self._preview_worker.preview_ready.connect(self._on_preview_ready)
        self._preview_worker.preview_failed.connect(self._on_preview_failed)
        self._preview_worker.finished.connect(self._on_preview_finished)
        self._preview_worker.start()

    def _on_preview_ready(self, title: str, additional_count: int) -> None:
        display_title = title if len(title) <= 30 else title[:30] + "..."
        text = f"검색된 제목: {display_title}"
        if additional_count:
            text += f" 외 {additional_count}개 영상"
        self.previewText.setText(text)

    def _on_preview_failed(self, message: str) -> None:
        self.previewText.setText("미리보기 정보를 가져오지 못했습니다.")
        QMessageBox.warning(self, "미리보기 실패", message)

    def _on_preview_finished(self) -> None:
        self.previewButton.setEnabled(self.convertButton.text() != "취소")
        self._preview_worker = None

    def _on_convert_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            # 변환 중 버튼을 다시 누르면 취소로 동작
            self._worker.cancel()
            self.convertButton.setEnabled(False)
            self.statusbar.showMessage("취소 요청 중...")
            return

        file_mode = self._is_file_mode()

        if file_mode:
            source = self.FilePathTextBox.text().strip()
            if not source:
                QMessageBox.warning(self, "입력 필요", "변환할 파일을 선택해 주세요.")
                return
            if not os.path.isfile(source):
                QMessageBox.warning(self, "파일 없음", "선택한 파일을 찾을 수 없습니다.")
                return
        else:
            source = self.URLtextB.text().strip()
            if not source:
                QMessageBox.warning(self, "입력 필요", "유튜브 URL을 입력해 주세요.")
                return

        output_dir = self.OutputTextB.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "입력 필요", "저장할 폴더를 선택해 주세요.")
            return

        ext = self._current_ext()
        quality = self.mediaComboBox.currentText()
        mode = "file" if file_mode else "url"

        self._start_conversion(mode, source, ext, quality, output_dir)

    def _start_conversion(self, mode: str, source: str, ext: str, quality: str,
                           output_dir: str) -> None:
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.statusbar.showMessage("준비 중...")

        self._worker = ConversionWorker(mode, source, ext, quality, output_dir)
        self._worker.progress_changed.connect(self._on_progress_changed)
        self._worker.status_changed.connect(self.statusbar.showMessage)
        self._worker.log_info.connect(self.logger.info)
        self._worker.log_error.connect(self.logger.error)
        self._worker.finished_ok.connect(self._on_finished_ok)
        self._worker.finished_error.connect(self._on_finished_error)

        self._set_ui_running(True)
        self._worker.start()

    def _on_progress_changed(self, percent: int) -> None:
        if percent < 0:
            # 진행률을 알 수 없는 구간: 마퀴(marquee) 표시
            if self.progressBar.maximum() != 0:
                self.progressBar.setRange(0, 0)
        else:
            if self.progressBar.maximum() == 0:
                self.progressBar.setRange(0, 100)
            self.progressBar.setValue(percent)

    def _on_finished_ok(self, output_path: str) -> None:
        self._set_ui_running(False)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(100)
        output_paths = output_path.splitlines()
        output_folder = os.path.dirname(output_paths[0])
        if len(output_paths) == 1:
            message = f"변환이 완료되었습니다:\n{output_paths[0]}\n\n결과 폴더를 열까요?"
            self.statusbar.showMessage(f"완료: {output_paths[0]}")
        else:
            message = (
                f"재생목록의 {len(output_paths)}개 영상 변환이 완료되었습니다.\n"
                f"저장 폴더: {output_folder}\n\n결과 폴더를 열까요?"
            )
            self.statusbar.showMessage(f"완료: {len(output_paths)}개 영상")

        reply = QMessageBox.information(
            self,
            "변환 완료",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._open_containing_folder(output_paths[0])

    def _on_finished_error(self, message: str) -> None:
        self._set_ui_running(False)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.statusbar.showMessage("오류 발생")
        QMessageBox.critical(self, "변환 실패", message)

    def _set_ui_running(self, running: bool) -> None:
        self.convertButton.setText("취소" if running else "Convert")
        self.convertButton.setEnabled(True)
        self.previewButton.setEnabled(not running)
        self.URLtextB.setEnabled(not running)
        self.FilePathTextBox.setEnabled(not running)
        self.FilePathButton.setEnabled(not running)
        self.URLRadioButton.setEnabled(not running)
        self.FileRadioButton.setEnabled(not running)
        self.formatComboBox.setEnabled(not running)
        self.mediaComboBox.setEnabled(not running)
        self.pathselectButton.setEnabled(not running)
        self.OutputTextB.setEnabled(not running)

    @staticmethod
    def _open_containing_folder(path: str) -> None:
        folder = os.path.dirname(path)
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except OSError:
            pass
