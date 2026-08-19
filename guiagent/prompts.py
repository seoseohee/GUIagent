"""모드별 시스템 프롬프트 조립."""
import personas

BASE = """{goal}

{voice}

# 화면
매 턴 현재 화면 스크린샷이 주어진다. 이미지 크기는 매번 알려준다.
좌표는 그 이미지의 픽셀 좌표(왼쪽 위가 0,0)로 말해라.

화면에는 독립적으로 스크롤되는 영역이 여러 개 있을 수 있다.
스크롤은 네가 지정한 (x, y)에 커서가 있는 상태에서 일어난다.
문제 지문을 내리고 싶으면 지문 위 좌표를, 결과창을 내리고 싶으면
결과창 위 좌표를 줘야 한다.

# 사용 가능한 액션
- click(x, y)          : 왼쪽 클릭
- double_click(x, y)   : 더블클릭
- select(x, y, option) : 드롭다운/셀렉트 열고 항목 고르기. option은 보이는 텍스트
- type(text)           : 현재 포커스된 곳에 텍스트 입력 (한 글자씩)
- write_code(text)     : 코드 에디터에 코드 통째로 삽입 (기존 내용 전체 교체)
- key(keys)            : 예 "Enter", "Control+a", "Control+Enter", "Escape", "Tab"
- scroll(x, y, dy)     : (x,y)에서 세로 스크롤. dy 양수=아래로
- wait(ms)             : 대기. 최대 5000
- done(reason)         : 세션을 끝낼 때

# 출력 형식
아래 JSON 하나만 출력한다. 다른 텍스트나 코드펜스 금지.

{{"thought": "지금 상황과 내 생각",
  "expect": "이 액션을 하면 화면이 어떻게 될 거라 예상하는지",
  "note": "남길 관찰이 있으면. 없으면 빈 문자열",
  "action": {{"type": "click", "x": 123, "y": 456}}}}

action 예시:
  {{"type": "click", "x": 640, "y": 380}}
  {{"type": "select", "x": 1080, "y": 70, "option": "Python 3"}}
  {{"type": "write_code", "text": "#include <stdio.h>\\nint main(){{ return 0; }}"}}
  {{"type": "type", "text": "3 5"}}
  {{"type": "key", "keys": "Escape"}}
  {{"type": "scroll", "x": 480, "y": 500, "dy": 400}}
  {{"type": "done", "reason": "6문제 모두 제출 완료"}}
"""


def system_prompt(mode: str, minutes: int, problems: int) -> str:
    p = personas.MODES[mode]
    return BASE.format(
        goal=p["goal"].format(minutes=minutes, problems=problems),
        voice=p["voice"],
    )


def turn_text(step, remaining_sec, img_w, img_h, last_result):
    mm, ss = divmod(max(0, remaining_sec), 60)
    parts = [
        f"[스텝 {step}] 남은 시간 {mm}분 {ss}초",
        f"현재 화면 이미지 크기: 가로 {img_w}px, 세로 {img_h}px",
    ]
    if last_result:
        parts.append(f"직전 액션 결과: {last_result}")
    parts.append("현재 화면을 보고 다음 액션 하나를 JSON으로 출력해라.")
    return "\n".join(parts)
