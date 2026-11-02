# MediaConverter

유튜브 영상/재생목록을 다운로드하거나 로컬 미디어 파일을 변환하는 Windows용
프로그램입니다 (mp3 / m4a / wav / flac / mp4 / mkv / avi / amv 지원).

## 실행에 필요한 것

이 프로그램에는 **FFmpeg**가 반드시 필요합니다. 별도로 설치할 필요는 없고,
`bin\ffmpeg.exe` / `bin\ffprobe.exe`로 이미 동봉되어 있습니다 (출처와 라이선스는
`bin\SOURCE.txt`, `THIRD-PARTY-NOTICES.txt` 참고). `bin\` 폴더를
`MediaConverter.exe`와 같은 폴더에 그대로 두면 됩니다.

혹시 `bin\ffmpeg.exe`가 없는 상태로 실행 중이라면(개발용 `python main.py` 실행 등),
시스템 PATH에 FFmpeg가 등록되어 있어야 합니다. 예:

```bat
winget install gyan.ffmpeg
```

## 개발자용 (소스 실행/빌드)

1. `.venv-win` 가상환경을 만들고 `requirements.txt`의 패키지를 설치합니다.
2. `start.bat` 으로 `python main.py` 실행 (개발/테스트용).
3. `build.bat` 으로 PyInstaller 빌드 (`dist\MediaConverter.exe` + `dist\bin\` 생성).

## 라이선스

이 프로젝트는 GNU General Public License v3 (GPL v3)로 배포됩니다. 전체 라이선스
전문은 [`LICENSE`](./LICENSE) 파일을 참고하세요.

이 프로그램은 FFmpeg 프로젝트의 라이브러리를 사용합니다
(<https://ffmpeg.org>, GPL v3로 빌드된 바이너리를 `bin\`에 동봉). 그 외
PyQt6, yt-dlp 등 사용한 타사 소프트웨어의 라이선스는
[`THIRD-PARTY-NOTICES.txt`](./THIRD-PARTY-NOTICES.txt)에 정리되어 있습니다.
