"""메인 루프. python agent.py 로 실행."""
import json
import os
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

import config
from actions import Executor
from model import QwenAgent
from vision import Frame

C = {"g": "\033[92m", "y": "\033[93m", "b": "\033[94m",
     "r": "\033[91m", "d": "\033[90m", "x": "\033[0m"}


def main():
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(config.RUN_DIR, run_id)
    os.makedirs(os.path.join(run_dir, "shots"), exist_ok=True)
    print(f"{C['d']}run: {run_dir}{C['x']}")
    print(f"{C['d']}모드: {config.MODE} | {config.SESSION_MINUTES}분 | "
          f"{config.PROBLEM_COUNT}문제 | {config.VIEWPORT['width']}x"
          f"{config.VIEWPORT['height']}{C['x']}\n")

    events = []          # 콘솔/네트워크 이벤트 (조용히 파일로만)
    trace = []           # 스텝별 기록

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx_kwargs = {"viewport": config.VIEWPORT, "device_scale_factor": 1}
        if config.RECORD_VIDEO:
            ctx_kwargs["record_video_dir"] = os.path.join(run_dir, "video")
            ctx_kwargs["record_video_size"] = config.VIEWPORT
        if config.STORAGE_STATE and os.path.exists(config.STORAGE_STATE):
            ctx_kwargs["storage_state"] = config.STORAGE_STATE

        ctx = browser.new_context(**ctx_kwargs)
        page = ctx.new_page()

        page.on("console", lambda m: m.type in ("error", "warning") and
                events.append({"t": time.time(), "kind": "console",
                               "msg": m.text[:300]}))
        page.on("pageerror", lambda e: events.append(
            {"t": time.time(), "kind": "pageerror", "msg": str(e)[:300]}))
        page.on("response", lambda r: r.status >= 400 and events.append(
            {"t": time.time(), "kind": "http", "msg": f"{r.status} {r.url[:200]}"}))

        page.goto(config.START_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        agent = QwenAgent()
        ex = Executor(page)

        deadline = time.time() + config.SESSION_MINUTES * 60
        last_result = ""
        step = 0

        try:
            while step < config.MAX_STEPS:
                remaining = int(deadline - time.time())
                if remaining <= 0:
                    print(f"{C['r']}⏰ 시간 종료{C['x']}")
                    break

                step += 1
                frame = Frame(page.screenshot())

                t0 = time.time()
                try:
                    out = agent.decide(frame, step, remaining, last_result)
                except Exception as e:
                    print(f"{C['r']}모델 호출 실패: {e}{C['x']}")
                    time.sleep(2)
                    continue
                latency = time.time() - t0

                thought = out.get("thought", "")
                expect = out.get("expect", "")
                note = out.get("note", "")
                action = out["action"]

                mm, ss = divmod(max(0, remaining), 60)
                print(f"{C['d']}── {step:>3}  남은시간 {mm:02d}:{ss:02d}  "
                      f"({latency:.1f}s){C['x']}")
                print(f"{C['b']}💭 {thought}{C['x']}")
                if expect:
                    print(f"{C['d']}   예상: {expect}{C['x']}")
                if note:
                    print(f"{C['y']}📝 {note}{C['x']}")
                if out.get("_error"):
                    print(f"{C['r']}   ⚠ {out['_error']}{C['x']}")

                result, click_pt = ex.run(action, frame)

                if click_pt and config.SAVE_OVERLAY:
                    frame.overlay(*click_pt, label=action.get("type", "")).save(
                        os.path.join(run_dir, "shots", f"{step:03d}.png"))
                else:
                    with open(os.path.join(run_dir, "shots", f"{step:03d}.png"),
                              "wb") as f:
                        f.write(frame.raw)

                mark = C['y'] if "변화 없음" in result or "실패" in result else C['g']
                print(f"{mark}▶ {action.get('type')} → {result}{C['x']}\n")

                agent.record(thought, action, result)
                trace.append({"step": step, "remaining": remaining,
                              "thought": thought, "expect": expect,
                              "note": note, "action": action,
                              "result": result})
                last_result = result

                if result == "DONE":
                    print(f"{C['g']}✅ 완료: "
                          f"{action.get('reason', '')}{C['x']}")
                    break

        except KeyboardInterrupt:
            print(f"\n{C['y']}중단됨{C['x']}")
        finally:
            with open(os.path.join(run_dir, "trace.json"), "w",
                      encoding="utf-8") as f:
                json.dump(trace, f, ensure_ascii=False, indent=2)
            with open(os.path.join(run_dir, "events.json"), "w",
                      encoding="utf-8") as f:
                json.dump(events, f, ensure_ascii=False, indent=2)
            ctx.close()
            browser.close()

    notes = [t for t in trace if t.get("note")]
    stuck = [t for t in trace if "변화 없음" in t["result"] or "실패" in t["result"]]
    print(f"\n{C['d']}스텝 {len(trace)} | 관찰 {len(notes)} | "
          f"무반응·실패 {len(stuck)} | 브라우저 이벤트 {len(events)}{C['x']}")
    if notes:
        print(f"\n{C['y']}── 남긴 관찰 ──{C['x']}")
        for t in notes:
            print(f"  [{t['step']:>3}] {t['note']}")
    if stuck:
        print(f"\n{C['r']}── 눌렀는데 반응 없던 지점 ──{C['x']}")
        for t in stuck:
            print(f"  [{t['step']:>3}] {t['action'].get('type')} — {t['result'][:70]}")
    print(f"\n{C['d']}→ {run_dir}{C['x']}")


if __name__ == "__main__":
    main()
