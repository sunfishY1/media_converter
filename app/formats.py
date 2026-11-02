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
출력 포맷(확장자) 및 품질 옵션 정의.

- FORMAT_TYPE: 확장자 -> "audio" | "video"
    -> 오디오 포맷은 yt-dlp에서 bestaudio 만 받아오고, 비디오 포맷은
       bestvideo+bestaudio 를 받아온 뒤 ffmpeg로 최종 인코딩한다.
- QUALITY_OPTIONS: 확장자 -> 콤보박스(mediaComboBox)에 표시할 품질 라벨 목록
- build_ffmpeg_args: 확장자 + 품질 라벨을 받아서 ffmpeg 인코딩 옵션(인자 리스트)을 만든다.
    (입력 "-i 파일", 출력 경로는 이 함수 밖에서 붙인다)
"""

from __future__ import annotations

# 콤보박스(formatComboBox)에 표시될 순서 (오디오 -> 비디오)
AUDIO_FORMATS = ["mp3", "m4a", "wav", "flac"]
VIDEO_FORMATS = ["mp4", "mkv", "avi", "amv"]
ALL_FORMATS = AUDIO_FORMATS + VIDEO_FORMATS

FORMAT_TYPE = {
    "mp3": "audio",
    "m4a": "audio",
    "wav": "audio",
    "flac": "audio",
    "mp4": "video",
    "mkv": "video",
    "avi": "video",
    "amv": "video",
}

# 확장자별 mediaComboBox 품질 옵션
QUALITY_OPTIONS = {
    "mp3": ["320 kbps", "256 kbps", "192 kbps", "128 kbps"],
    "m4a": ["320 kbps", "256 kbps", "192 kbps", "128 kbps"],
    "wav": ["48000 Hz (원본 그대로)"],
    "flac": ["무손실 (Lossless)"],
    "mp4": ["원본 해상도", "1080p", "720p", "480p", "360p"],
    "mkv": ["원본 해상도", "1080p", "720p", "480p", "360p"],
    "avi": ["원본 해상도", "720p", "480p", "360p"],
    # AMV는 옛 저가형 MP3/MP4 플레이어(액션세미컨덕터 계열) 전용 포맷이라
    # 해상도가 매우 작아야 정상 재생된다.
    "amv": [
        "160x120 (표준)",
        "128x96",
        "176x144",
        "208x176",
    ],
}

# 해상도 라벨(1080p 등) -> 세로 픽셀 수
_HEIGHT_BY_LABEL = {
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
}


def is_audio_format(ext: str) -> bool:
    return FORMAT_TYPE.get(ext, "video") == "audio"


def default_quality(ext: str) -> str:
    options = QUALITY_OPTIONS.get(ext, [])
    return options[0] if options else ""


def _bitrate_to_k(label: str) -> str:
    # "320 kbps" -> "320k"
    digits = "".join(ch for ch in label if ch.isdigit())
    return f"{digits or '192'}k"


def _parse_amv_resolution(label: str) -> tuple[int, int]:
    # "160x120 (표준)" -> (160, 120)
    head = label.split(" ")[0]
    w_str, h_str = head.lower().split("x")
    return int(w_str), int(h_str)


# 영상/음원마다 들쭉날쭉한 음량을 일정한 수준으로 맞춰주는 음량 표준화
# (EBU R128 loudnorm) 필터. 사용자가 따로 설정하지 않아도 모든 변환에
# 기본값으로 적용한다.
_LOUDNORM_ARGS = ["-af", "loudnorm"]

# mp3(libmp3lame) VBR 품질 스케일(-q:a, 0=최고 품질 ~220~260kbps 평균,
# 9=최저 ~65kbps 평균). 기존 비트레이트 라벨과 평균 비트레이트가 비슷하게
# 나오도록 매핑한다. CBR(-b:a)보다 같은 용량 대비 음질이 더 좋아서 VBR을
# 기본값으로 사용한다.
_MP3_VBR_Q_BY_LABEL = {
    "320 kbps": "0",
    "256 kbps": "1",
    "192 kbps": "2",
    "128 kbps": "5",
}


def build_ffmpeg_args(ext: str, quality: str) -> list[str]:
    """확장자 + 품질 라벨 -> ffmpeg 인코딩 옵션 리스트 (입력/출력 경로 제외)"""

    if ext == "mp3":
        vbr_q = _MP3_VBR_Q_BY_LABEL.get(quality, "2")
        return ["-vn", "-acodec", "libmp3lame", "-q:a", vbr_q, *_LOUDNORM_ARGS]

    if ext == "m4a":
        # 참고: ffmpeg 내장 aac 인코더는 VBR 모드 품질이 라이브러리별로 들쭉날쭉
        # 하다고 공식적으로 알려져 있어서(libfdk_aac 같은 더 나은 VBR 인코더는
        # 라이선스 문제로 GPL 빌드에 포함되지 않음), m4a는 안정적인 CBR을
        # 그대로 유지한다.
        return ["-vn", "-acodec", "aac", "-b:a", _bitrate_to_k(quality), *_LOUDNORM_ARGS]

    if ext == "wav":
        return ["-vn", "-acodec", "pcm_s16le", *_LOUDNORM_ARGS]

    if ext == "flac":
        return ["-vn", "-acodec", "flac", *_LOUDNORM_ARGS]

    if ext in ("mp4", "mkv"):
        args = ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k", *_LOUDNORM_ARGS]
        height = _HEIGHT_BY_LABEL.get(quality)
        if height:
            # 가로는 짝수 유지를 위해 -2 사용
            args += ["-vf", f"scale=-2:{height}"]
        return args

    if ext == "avi":
        args = ["-c:v", "mpeg4", "-vtag", "xvid", "-q:v", "5",
                "-c:a", "libmp3lame", "-b:a", "192k", *_LOUDNORM_ARGS]
        height = _HEIGHT_BY_LABEL.get(quality)
        if height:
            args += ["-vf", f"scale=-2:{height}"]
        return args

    if ext == "amv":
        width, height = _parse_amv_resolution(quality)

        # YouTube 원본은 대부분 limited(tv) 색 범위의 yuv420p 인데, amv가 요구하는
        # yuvj420p는 full(pc) 범위다. 단순히 -pix_fmt로 태그만 바꾸면 값 자체는
        # 재계산되지 않아서(0~255 전체를 못 씀) 결과물이 어둡고 대비가 낮게 나온다.
        # scale 필터에서 in_range=tv:out_range=pc 로 실제 픽셀 값을 재매핑해서
        # 이 문제를 해결하고, eq 필터로 약간의 밝기를 추가 보정한다.
        vf = (
            f"scale={width}:{height}:in_range=tv:out_range=pc,"
            "format=yuvj420p,"
            "eq=brightness=0.03:contrast=1.05"
        )

        return [
            "-r", "15",
            "-vf", vf,
            *_LOUDNORM_ARGS,
            "-c:v", "amv",
            "-c:a", "adpcm_ima_amv",
            "-ar", "22050",
            "-ac", "1",
            "-block_size", "1470",
            "-strict", "-1",
            "-f", "amv",
        ]

    raise ValueError(f"지원하지 않는 포맷입니다: {ext}")
