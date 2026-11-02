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
유튜브 -> mp3/mp4/amv 등 변환 프로그램 진입점.

실행: (가상환경 활성화 후)
    python main.py
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
