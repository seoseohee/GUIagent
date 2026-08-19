# GUIagent-goormghost
for enhancing UX

https://claude.ai/code/artifact/3ebdf584-ec60-4691-b5b0-c718512eec3d

코딩테스트 플랫폼을 에이전트가 실제 응시자처럼 응시해보는 GUI 에이전트.
화면 캡처 → Qwen VL이 판단 → 마우스·키보드 조작 → 반복.

목적은 문제를 잘 푸는 게 아니라 **어디서 헤매는지 보는 것**.

---

## 두 가지 버전

### simple.py — 내 브라우저를 그대로 쓰는 버전 (메인)

```bash
pip install mss pyautogui pillow openai
# 브라우저로 시험 화면 직접 띄우고 로그인까지 해둔다
python simple.py
```

3초 뒤 시작. 실제 마우스가 움직인다.
**멈추려면 마우스를 화면 왼쪽 위 구석으로 확 민다** (pyautogui 페일세이프).

실행 환경이 실사용자와 100% 같다는 게 장점. 대신 도는 동안 컴퓨터를 못 쓴다.

### agent.py — Playwright 버전

```bash
pip install -r requirements.txt && playwright install chromium
export CTA_URL="https://플랫폼주소/문제/1"
CTA_MODE=examinee  python agent.py   # 응시자 모드
CTA_MODE=inspector python agent.py   # 검수자 모드
```

별도 브라우저 창을 띄우므로 백그라운드 실행 가능.
"클릭했는데 화면 변화 없음" 같은 신호를 자동 수집.
로그인이 필요하면 `python save_login.py` 먼저 실행 → `CTA_STORAGE_STATE=auth.json`

---

## 모델 붙이기

셋 다 코드는 동일하다. `BASE_URL`만 다르다.

```python
BASE_URL = "http://localhost:8000/v1"      # 로컬 GPU
BASE_URL = "https://xxxx.ngrok.io/v1"      # 콜랩 + 터널
BASE_URL = "https://openrouter.ai/api/v1"  # API
```

로컬 서빙 예시:
```bash
vllm serve Qwen/Qwen3-VL-8B-Instruct \
  --max-model-len 32768 \
  --limit-mm-per-prompt image=4 \
  --gpu-memory-utilization 0.90
```

---

## 두 모드 (personas.py)

| | 응시자 모드 | 검수자 모드 |
|---|---|---|
| 목표 | 문제 풀기 | 문제 확인하기 |
| 잡는 것 | UI 마찰·발견성 | 콘텐츠 누락·오류 |
| 판정 | 해석 필요 | 자기완결적 |
| 언어 | 하나면 됨 | 전부 돌려야 함 |

**응시자 모드**는 기능 목록을 주지 않는다. 목록을 주는 순간 순서대로 눌러버려서
헤매는 궤적이 사라진다. "검수", "버그" 같은 단어도 프롬프트에 넣지 않는다.

**검수자 모드**는 출제 원본 없이 화면 안의 모순만으로 판정한다.
지문이 곧 스펙이다. 핵심은 언어 간 교차 검증 — 같은 문제를 허용된 모든 언어로
풀어서, 결과가 다르면 정답을 몰라도 그 자체가 버그다.

---

## 첫 실행에서 볼 것

`shots/` 안의 빨간 표적이 실제 누르려던 버튼 위에 찍히는지 확인한다.

- 대체로 맞음 → 그냥 30분 돌린다
- **항상 좌상단에 몰림** → 모델이 0~1000 정규화 좌표를 뱉는 것.
  `simple.py`는 좌표 변환부를, `agent.py`는 `CTA_COORD_MODE=normalized_1000`으로
- 그 외 패턴으로 어긋남 → 캡처 해상도와 뷰포트 설정 확인

---

## 현실적 기대치

30분에 1~2문제 건드리다 끝난다. 클릭은 자주 빗나가고, 막히면 같은 자리를
반복해서 누른다. 그래도 실패가 아니다 — 1번 문제 붙잡고 20분 헤매는 동안
`실행`/`테스트` 헷갈리는 장면이 나오면 그게 수확이다.

**모델 한계와 UI 결함을 구분할 것:**

| 관찰 | 해석 |
|---|---|
| 버튼을 찾았는데 몇 px 빗나감 | 모델 문제. 버림 |
| 지문 안 읽고 헤맴 | 모델 문제. 버림 |
| **버튼은 보이는데 뭘 눌러야 할지 모름** | **UI 문제. 이게 수확** |
| 안내 다 읽고도 뭘 해야 할지 모름 | UI/안내 문제 |

---

## 파일

```
simple.py      한 파일 완결. 화면 캡처 + 실제 마우스 조작
agent.py       Playwright 메인 루프
personas.py    두 모드 프롬프트. 여기가 실험의 핵심
prompts.py     모드별 시스템 프롬프트 조립
vision.py      smart_resize + 좌표 역변환 + 오버레이 디버거
actions.py     클릭·타이핑·드롭다운·Monaco 코드 입력
model.py       Qwen 클라이언트 + 컨텍스트 관리 + JSON 파서
config.py      설정. 뷰포트·세션 시간·모델 전부 여기
save_login.py  로그인 세션 저장
```

## 아직 안 만든 것

세션 리포트. 지금은 `trace.json`과 `shots/`만 남는다.
검수자가 볼 수 있는 형태(막힌 지점별 스크린샷 + 혼잣말 + 소요 스텝)로
정리하는 부분이 필요하다. trace를 별도 모델에 던져 제3자 시점으로
정리시키는 쪽을 권함 — 겪은 에이전트가 회고하면 미화한다.
