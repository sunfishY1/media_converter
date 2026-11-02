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
LogPlaneTextBox(QPlainTextEdit)에 타임스탬프 + 색상이 있는 로그를 출력하는 헬퍼.

- INFO  : "HH:MM:SS [INFO] 메세지"  (녹색)
- ERROR : "HH:MM:SS [ERROR] 메세지" (빨간색)

타임스탬프는 가독성을 위해 회색으로, [INFO]/[ERROR] 태그와 메세지는 레벨에 맞는
색으로 표시한다. QPlainTextEdit은 기본적으로 일반 텍스트 위젯이지만
appendHtml()을 통해 줄 단위로 색이 있는 HTML을 추가할 수 있다.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from PyQt6.QtWidgets import QPlainTextEdit

_COLOR_TIME = "#666666"
_COLOR_INFO = "#1b8a2f"
_COLOR_ERROR = "#d32f2f"


class Logger:
    def __init__(self, text_box: QPlainTextEdit):
        self._box = text_box

    def _emit(self, level: str, color: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        safe_message = escape(str(message))
        html = (
            f'<span style="color:{_COLOR_TIME};">{timestamp}</span> '
            f'<span style="color:{color};">[{level}] {safe_message}</span>'
        )
        self._box.appendHtml(html)
        scrollbar = self._box.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.maximum())

    def info(self, message: str) -> None:
        self._emit("INFO", _COLOR_INFO, message)

    def error(self, message: str) -> None:
        self._emit("ERROR", _COLOR_ERROR, message)