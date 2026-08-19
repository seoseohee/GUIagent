"""화면 그대로 캡처해서 실제 마우스/키보드를 움직이는 최소 버전.

쓰는 법:
  1. pip install mss pyautogui pillow openai
  2. 브라우저로 코딩테스트 화면 직접 띄우고 로그인까지 해둔다
  3. python simple.py
  4. 3초 뒤 시작. 멈추려면 마우스를 화면 왼쪽 위 구석으로 확 밀면 됨.

주의: 얘가 진짜 네 마우스를 움직인다. 다른 창 만지지 마라.
"""
import base64
import io
import json
import math
import re
import time

import os

import mss
import pyautogui
from openai import OpenAI
from PIL import Image, ImageDraw

BASE_URL = "http://localhost:8000/v1"
MODEL = "Qwen/Qwen3-VL-8B-Instruct"
MINUTES = 30
MAX_PIXELS = 1600 * 28 * 28   # 모델에 넣는 이미지 예산
HIST_BUDGET = 40000           # 히스토리 글자 상한. vLLM --max-model-len에 맞춰 조정

SAVE_SHOTS = True             # 클릭 지점에 빨간 점 찍어 저장. 좌표 검증에 필수
SHOT_DIR = "shots"

pyautogui.FAILSAFE = True     # 마우스 좌상단으로 밀면 강제 중단
client = OpenAI(base_url=BASE_URL, api_key="EMPTY")

SYSTEM = """너는 온라인 코딩테스트를 응시하는 개발자다. 제한시간 30분.
화면에 보이는 것만으로 판단해서 문제를 풀고 제출해라.

혼잣말(thought)에는 지금 뭘 하려는지, 뭘 예상하는지 그대로 적어라.
헷갈리면 헷갈린다고, 어디 눌러야 할지 모르겠으면 모르겠다고 써라.

화면에 안내나 팝업이 뜨면, 닫기 전에 내용을 끝까지 읽어라.
스크롤이 있으면 내려서 다 본다. 나중에 필요할 것 같은 내용은 thought에 적어둬라.

액션:
  click(x,y) / double_click(x,y) / type(text) / key(keys)
  scroll(x,y,dy)  dy 양수=아래 / wait(ms) / done(reason)
key 예시: "enter", "ctrl+a", "ctrl+enter", "escape", "tab"

아래 JSON 하나만 출력. 코드펜스 금지.
{"thought":"...","expect":"...","action":{"type":"click","x":100,"y":200}}"""


def grab():
    """화면 캡처 → (원본이미지, 모델용 리사이즈, 스케일)"""
    with mss.mss() as sct:
        mon = sct.monitors[1]                      # 주 모니터
        raw = sct.grab(mon)
    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    W, H = img.size

    # Qwen은 28의 배수로 리사이즈하므로 미리 그 크기로 맞춰 보낸다
    f = 28
    w, h = round(W / f) * f, round(H / f) * f
    if w * h > MAX_PIXELS:
        beta = math.sqrt(W * H / MAX_PIXELS)
        w = max(f, int(W / beta / f) * f)
        h = max(f, int(H / beta / f) * f)
    small = img.resize((w, h), Image.LANCZOS)
    return img, small, (W / w, H / h), mon["left"], mon["top"]


def pack(history, budget=HIST_BUDGET):
    """최근 것부터 예산 안에서 채운다. 스텝 수가 아니라 글자 수로 자른다."""
    out, total = [], 0
    for line in reversed(history):
        if total + len(line) > budget:
            break
        out.append(line)
        total += len(line)
    return "\n".join(reversed(out))


def ask(small, history, step, remaining):
    buf = io.BytesIO()
    small.save(buf, format="PNG")
    url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    mm, ss = divmod(max(0, remaining), 60)

    msgs = [{"role": "system", "content": SYSTEM}]
    if history:
        msgs.append({"role": "user",
                     "content": "[지금까지]\n" + pack(history)})
    msgs.append({"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": url}},
        {"type": "text",
         "text": f"[스텝 {step}] 남은 시간 {mm}분 {ss}초\n"
                 f"이미지 크기 {small.width}x{small.height}\n"
                 "다음 액션 하나를 JSON으로."},
    ]})
    txt = client.chat.completions.create(
        model=MODEL, messages=msgs, temperature=0.3, max_tokens=800
    ).choices[0].message.content or ""

    txt = re.sub(r"```(?:json)?|```", "", txt).strip()
    try:
        return json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
    except Exception:
        return {"thought": txt[:200], "expect": "",
                "action": {"type": "wait", "ms": 800}}


def mark(img, x, y, step, label):
    """클릭 지점에 표적을 그려 저장. 좌표가 어긋나면 이걸 봐야 원인을 안다."""
    im = img.copy()
    d = ImageDraw.Draw(im)
    r = 16
    d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 0, 0), width=3)
    d.line([x - r * 2, y, x + r * 2, y], fill=(255, 0, 0), width=1)
    d.line([x, y - r * 2, x, y + r * 2], fill=(255, 0, 0), width=1)
    d.text((x + r + 6, y - 8), label, fill=(255, 0, 0))
    im.save(os.path.join(SHOT_DIR, f"{step:03d}.png"))


def do(a, sx, sy, ox, oy, img=None, step=0):
    t = a.get("type", "")
    if t in ("click", "double_click", "scroll"):
        x = ox + float(a.get("x", 0)) * sx
        y = oy + float(a.get("y", 0)) * sy
        if t == "scroll":
            pyautogui.moveTo(x, y)
            pyautogui.scroll(-int(a.get("dy", 300)))   # pyautogui는 부호 반대
            return f"스크롤 {a.get('dy')}"
        if SAVE_SHOTS and img is not None:
            mark(img, x - ox, y - oy, step, t)          # 저장은 캡처 좌표계로
        pyautogui.moveTo(x, y, duration=0.3)           # 눈으로 따라가게 천천히
        pyautogui.click(clicks=2 if t == "double_click" else 1, interval=0.1)
        return f"({x:.0f},{y:.0f}) {t}"
    if t == "type":
        pyautogui.write(a.get("text", ""), interval=0.02)
        return f"{len(a.get('text',''))}자 입력"
    if t == "key":
        pyautogui.hotkey(*[k.strip().lower() for k in a.get("keys", "").split("+")])
        return f"키 {a.get('keys')}"
    if t == "wait":
        time.sleep(min(int(a.get("ms", 800)), 5000) / 1000)
        return "대기"
    if t == "done":
        return "DONE"
    return f"모르는 액션 {t}"


def main():
    if SAVE_SHOTS:
        os.makedirs(SHOT_DIR, exist_ok=True)
    print("3초 뒤 시작. 시험 화면을 앞에 띄워둬라.")
    print("멈추려면 마우스를 화면 왼쪽 위 구석으로 확 밀면 된다.\n")
    time.sleep(3)

    end = time.time() + MINUTES * 60
    history, step = [], 0

    while step < 200 and time.time() < end:
        step += 1
        img, small, (sx, sy), ox, oy = grab()
        out = ask(small, history, step, int(end - time.time()))

        print(f"\n── {step}  💭 {out.get('thought','')}")
        if out.get("expect"):
            print(f"   예상: {out['expect']}")

        result = do(out["action"], sx, sy, ox, oy, img, step)
        print(f"   ▶ {result}")

        history.append(f"{step}. {out.get('thought','')} → {result}")
        if result == "DONE":
            print(f"\n✅ {out['action'].get('reason','')}")
            break
        time.sleep(0.8)   # 화면 반영 대기


if __name__ == "__main__":
    main()
