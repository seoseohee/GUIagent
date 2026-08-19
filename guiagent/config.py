"""전체 설정. 여기만 고치면 대부분 대응됨."""
import os

# ── 모드 ──────────────────────────────────────────────────────────
# "examinee"  = 진짜 응시자처럼 (기능 목록 모름, 헤매는 궤적이 결과물)
# "inspector" = 1차 검수자 (기능 체크리스트 순회, 커버리지가 결과물)
MODE = os.getenv("CTA_MODE", "examinee")

# ── 대상 ──────────────────────────────────────────────────────────
START_URL = os.getenv("CTA_URL", "https://example.com")
PROBLEM_COUNT = int(os.getenv("CTA_PROBLEMS", "6"))

# 로그인이 필요하면 storage_state 파일 경로 지정 (없으면 None)
# 만드는 법: python save_login.py  (README 참고)
STORAGE_STATE = os.getenv("CTA_STORAGE_STATE") or None

# ── 모델 ──────────────────────────────────────────────────────────
# vLLM 로컬 서빙이든 DashScope든 OpenAI 호환 엔드포인트면 다 됨
BASE_URL = os.getenv("CTA_BASE_URL", "http://localhost:8000/v1")
API_KEY = os.getenv("CTA_API_KEY", "EMPTY")
MODEL = os.getenv("CTA_MODEL", "Qwen/Qwen3-VL-8B-Instruct")

TEMPERATURE = 0.3
MAX_TOKENS = 1024

# 좌표 출력 방식. 대부분 "absolute"(이미지 픽셀 좌표).
# 오버레이 디버그 보고 점이 항상 좌상단에 몰리면 "normalized_1000"으로 바꿔볼 것.
COORD_MODE = os.getenv("CTA_COORD_MODE", "absolute")

# ── 이미지 ────────────────────────────────────────────────────────
# 실제 응시 화면과 같은 크기여야 한다. 좁으면 레이아웃이 접혀서
# 실사용자가 보는 것과 다른 화면을 관찰하게 됨.
VIEWPORT = {"width": 1600, "height": 900}

# 모델에 넣는 이미지 픽셀 예산. 크면 grounding 정확도↑ 토큰/지연↑
# 28*28 = 1패치. 1,003,520 ≈ 1280x800 정도를 거의 원본으로 보냄
MAX_PIXELS = 1600 * 28 * 28   # ≈ 1,254,400 (1600x900을 거의 원본으로)
MIN_PIXELS = 256 * 28 * 28

# ── 세션 예산 ─────────────────────────────────────────────────────
SESSION_MINUTES = int(os.getenv("CTA_MINUTES", "30"))
MAX_STEPS = int(os.getenv("CTA_MAX_STEPS", "180"))

# 모델에 실제로 넣는 최근 스크린샷 개수 (나머지는 텍스트 요약만)
RECENT_IMAGES = 3

# 액션 후 기본 대기(ms)
ACTION_SETTLE_MS = 700

# ── 출력 ──────────────────────────────────────────────────────────
RUN_DIR = os.getenv("CTA_RUN_DIR", "./runs")
RECORD_VIDEO = True
SAVE_OVERLAY = True   # 클릭 지점 빨간 점 찍은 디버그 이미지 저장
