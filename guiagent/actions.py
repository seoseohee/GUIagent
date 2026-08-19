"""모델이 낸 액션을 실제 브라우저 조작으로 옮긴다."""
import config

KEY_ALIASES = {
    "ctrl": "Control", "cmd": "Meta", "esc": "Escape",
    "enter": "Enter", "return": "Enter", "tab": "Tab",
    "backspace": "Backspace", "delete": "Delete", "space": " ",
    "up": "ArrowUp", "down": "ArrowDown",
    "left": "ArrowLeft", "right": "ArrowRight",
}


def _norm_keys(keys: str) -> str:
    out = []
    for part in str(keys).split("+"):
        p = part.strip()
        out.append(KEY_ALIASES.get(p.lower(), p if len(p) > 1 else p.lower()))
    return "+".join(out)


class Executor:
    def __init__(self, page):
        self.page = page

    def run(self, action: dict, frame) -> tuple[str, tuple | None]:
        """액션 실행. (사람이 읽을 결과 문자열, 클릭좌표 or None) 반환."""
        t = (action.get("type") or "").lower()

        try:
            if t in ("click", "double_click", "right_click"):
                return self._click(t, action, frame)
            if t == "select":
                return self._select(action, frame)
            if t == "type":
                return self._type(action)
            if t == "write_code":
                return self._write_code(action)
            if t == "key":
                return self._key(action)
            if t == "scroll":
                return self._scroll(action, frame)
            if t == "wait":
                ms = min(int(action.get("ms", 1000)), 5000)
                self.page.wait_for_timeout(ms)
                return f"{ms}ms 대기함", None
            if t == "done":
                return "DONE", None
            return f"알 수 없는 액션 타입: {t}", None
        except Exception as e:
            return f"액션 실패: {type(e).__name__}: {e}", None

    # ── 개별 액션 ────────────────────────────────────────────────
    def _click(self, t, action, frame):
        x, y = frame.to_browser(float(action["x"]), float(action["y"]))
        before = self._fingerprint()
        if t == "click":
            self.page.mouse.click(x, y)
        elif t == "double_click":
            self.page.mouse.dblclick(x, y)
        else:
            self.page.mouse.click(x, y, button="right")
        self._settle()
        changed = self._fingerprint() != before
        note = "" if changed else " (화면 변화 없음)"
        return f"({x:.0f}, {y:.0f}) {t}{note}", (x, y)

    def _select(self, action, frame):
        """드롭다운 선택. 네이티브 <select>면 그걸로, 아니면 열고 항목 클릭."""
        x, y = frame.to_browser(float(action["x"]), float(action["y"]))
        option = str(action.get("option", "")).strip()

        # 1) 네이티브 select인지 확인
        try:
            tag = self.page.evaluate(
                "([x,y]) => { const e = document.elementFromPoint(x,y);"
                " return e ? e.closest('select') ? 'select' : e.tagName : ''; }",
                [x, y])
        except Exception:
            tag = ""

        if tag == "select":
            loc = self.page.locator("select").nth(0)
            try:
                loc.select_option(label=option)
                self._settle()
                return f"드롭다운에서 '{option}' 선택", (x, y)
            except Exception:
                pass

        # 2) 커스텀 드롭다운: 열고 → 보이는 텍스트로 항목 클릭
        self.page.mouse.click(x, y)
        self.page.wait_for_timeout(500)
        try:
            item = self.page.get_by_text(option, exact=False).last
            item.click(timeout=2500)
            self._settle()
            return f"드롭다운 열고 '{option}' 클릭", (x, y)
        except Exception:
            self._settle()
            return (f"드롭다운은 열렸으나 '{option}' 항목을 못 찾음 "
                    f"(화면에 보이는 항목을 직접 click 해야 함)"), (x, y)

    def _type(self, action):
        text = action.get("text", "")
        self.page.keyboard.type(text, delay=25)
        self._settle()
        return f"{len(text)}자 입력함", None

    def _write_code(self, action):
        """코드 에디터에 코드 삽입.

        Monaco/CodeMirror는 keydown에 반응해서 자동 들여쓰기·괄호 자동완성을
        걸어버리므로, 한 글자씩 타이핑하면 코드가 망가진다.
        insert_text는 키 이벤트 없이 텍스트를 넣어서 그 문제를 피한다.
        """
        text = action.get("text", "")
        self.page.keyboard.press("Control+a")
        self.page.wait_for_timeout(80)
        self.page.keyboard.press("Delete")
        self.page.wait_for_timeout(80)
        self.page.keyboard.insert_text(text)
        self._settle()
        lines = text.count("\n") + 1
        return f"코드 {lines}줄 작성함", None

    def _key(self, action):
        keys = _norm_keys(action.get("keys", ""))
        if not keys:
            return "키 입력값 없음", None
        self.page.keyboard.press(keys)
        self._settle()
        return f"키 입력: {keys}", None

    def _scroll(self, action, frame):
        x, y = frame.to_browser(float(action.get("x", 640)),
                                float(action.get("y", 400)))
        dy = int(action.get("dy", 300))
        self.page.mouse.move(x, y)
        self.page.mouse.wheel(0, dy)
        self._settle()
        return f"스크롤 {dy:+d}", None

    # ── 보조 ─────────────────────────────────────────────────────
    def _settle(self):
        self.page.wait_for_timeout(config.ACTION_SETTLE_MS)
        try:
            self.page.wait_for_load_state("networkidle", timeout=2500)
        except Exception:
            pass  # SPA는 networkidle이 안 올 수 있음. 무시.

    def _fingerprint(self) -> str:
        """클릭이 먹었는지 판단용 가벼운 DOM 지문."""
        try:
            return self.page.evaluate(
                "() => document.body.innerText.length + '|' "
                "+ document.querySelectorAll('*').length + '|' + location.href"
            )
        except Exception:
            return ""
