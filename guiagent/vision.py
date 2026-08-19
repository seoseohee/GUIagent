"""스크린샷 → 모델 입력 이미지 변환, 그리고 모델 좌표 → 브라우저 좌표 역변환.

이 프로젝트에서 제일 자주 깨지는 게 좌표라서 여기가 핵심이다.

전략:
  Qwen VL 계열은 서버에서 smart_resize(28의 배수로 맞추고 픽셀 예산 안으로 축소)를
  한 번 더 돌린다. 그 결과 크기를 우리가 모르면 좌표 역변환이 틀어진다.
  그래서 **우리가 먼저 smart_resize 결과 크기로 리사이즈해서 보낸다.**
  그러면 서버 쪽 smart_resize는 항등변환이 되고, 스케일 비율을 정확히 알 수 있다.
"""
import base64
import io
import math

from PIL import Image, ImageDraw

import config

FACTOR = 28  # Qwen2-VL/2.5-VL/3-VL 공통 패치 그리드


def _round_by(n: float, f: int) -> int:
    return int(round(n / f) * f)


def _floor_by(n: float, f: int) -> int:
    return int(math.floor(n / f) * f)


def _ceil_by(n: float, f: int) -> int:
    return int(math.ceil(n / f) * f)


def smart_resize(h: int, w: int,
                 factor: int = FACTOR,
                 min_pixels: int = config.MIN_PIXELS,
                 max_pixels: int = config.MAX_PIXELS):
    """Qwen VL 프로세서의 smart_resize와 동일한 로직."""
    h_bar = max(factor, _round_by(h, factor))
    w_bar = max(factor, _round_by(w, factor))
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((h * w) / max_pixels)
        h_bar = max(factor, _floor_by(h / beta, factor))
        w_bar = max(factor, _floor_by(w / beta, factor))
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (h * w))
        h_bar = _ceil_by(h * beta, factor)
        w_bar = _ceil_by(w * beta, factor)
    return h_bar, w_bar


class Frame:
    """한 장의 스크린샷 + 좌표 변환 정보."""

    def __init__(self, png_bytes: bytes):
        self.raw = png_bytes
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        self.orig_w, self.orig_h = img.size

        model_h, model_w = smart_resize(self.orig_h, self.orig_w)
        self.model_w, self.model_h = model_w, model_h
        self.resized = img.resize((model_w, model_h), Image.LANCZOS)

        # 모델 좌표 → 원본(=브라우저 CSS 픽셀) 좌표 스케일
        self.sx = self.orig_w / model_w
        self.sy = self.orig_h / model_h

    def data_url(self) -> str:
        buf = io.BytesIO()
        self.resized.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"

    def to_browser(self, x: float, y: float):
        """모델이 뱉은 좌표를 브라우저 클릭 좌표로."""
        if config.COORD_MODE == "normalized_1000":
            bx = x / 1000.0 * self.orig_w
            by = y / 1000.0 * self.orig_h
        else:
            bx = x * self.sx
            by = y * self.sy
        # 뷰포트 밖으로 나가지 않게 클램프
        bx = max(0, min(self.orig_w - 1, bx))
        by = max(0, min(self.orig_h - 1, by))
        return round(bx, 1), round(by, 1)

    def overlay(self, x: float, y: float, label: str = "") -> Image.Image:
        """디버그용: 클릭 지점에 빨간 표적 그리기 (브라우저 좌표 기준)."""
        img = Image.open(io.BytesIO(self.raw)).convert("RGB")
        d = ImageDraw.Draw(img)
        r = 14
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 0, 0), width=3)
        d.line([x - r * 2, y, x + r * 2, y], fill=(255, 0, 0), width=1)
        d.line([x, y - r * 2, x, y + r * 2], fill=(255, 0, 0), width=1)
        if label:
            d.text((x + r + 4, y - 8), label[:60], fill=(255, 0, 0))
        return img
