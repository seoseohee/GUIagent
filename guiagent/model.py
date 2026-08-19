"""Qwen VL 호출 + 응답 파싱 + 컨텍스트 관리."""
import json
import re

from openai import OpenAI

import config
import prompts


class QwenAgent:
    def __init__(self):
        self.client = OpenAI(base_url=config.BASE_URL, api_key=config.API_KEY)
        self.system = prompts.system_prompt(
            config.MODE, config.SESSION_MINUTES, config.PROBLEM_COUNT)
        # 전체 이력은 텍스트로만 누적하고, 이미지는 최근 것만 붙인다.
        self.log: list[dict] = []          # {"thought","action","result"}
        self.frames: list[tuple] = []      # (data_url, turn_text)

    def decide(self, frame, step: int, remaining_sec: int, last_result: str) -> dict:
        turn = prompts.turn_text(step, remaining_sec,
                                 frame.model_w, frame.model_h, last_result)
        self.frames.append((frame.data_url(), turn))
        self.frames = self.frames[-config.RECENT_IMAGES:]

        messages = [{"role": "system", "content": self.system}]

        # 오래된 스텝은 텍스트 요약으로만
        old = self.log[:-config.RECENT_IMAGES] if len(self.log) > config.RECENT_IMAGES else []
        if old:
            summary = "\n".join(
                f"{i+1}. {e['thought'][:110]} → {e['action']} → {e['result'][:70]}"
                for i, e in enumerate(old)
            )
            messages.append({
                "role": "user",
                "content": f"[지금까지 한 일 요약]\n{summary}",
            })

        # 최근 스텝은 이미지까지
        for data_url, txt in self.frames:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": txt},
                ],
            })

        resp = self.client.chat.completions.create(
            model=config.MODEL,
            messages=messages,
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS,
        )
        raw = resp.choices[0].message.content or ""
        return parse(raw)

    def record(self, thought: str, action: dict, result: str):
        self.log.append({
            "thought": thought,
            "action": json.dumps(action, ensure_ascii=False),
            "result": result,
        })


def parse(raw: str) -> dict:
    """모델 출력에서 JSON 하나를 뽑아낸다. 코드펜스/잡설 섞여도 견딤."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()

    # 첫 번째 균형 잡힌 {...} 블록 찾기
    start = text.find("{")
    if start == -1:
        return {"thought": raw[:300], "action": {"type": "wait", "ms": 800},
                "_error": "JSON 없음"}

    depth, end, in_str, esc = 0, None, False, False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return {"thought": raw[:300], "action": {"type": "wait", "ms": 800},
                "_error": "JSON 안 닫힘"}

    try:
        obj = json.loads(text[start:end])
    except json.JSONDecodeError as e:
        return {"thought": raw[:300], "action": {"type": "wait", "ms": 800},
                "_error": f"JSON 파싱 실패: {e}"}

    if not isinstance(obj.get("action"), dict):
        obj["action"] = {"type": "wait", "ms": 800}
        obj["_error"] = "action 필드 없음"
    obj.setdefault("thought", "")
    obj.setdefault("expect", "")
    obj.setdefault("note", "")
    return obj
