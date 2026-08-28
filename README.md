
# goormghost

A GUI agent that sits a coding test the way a real candidate would.
Capture the screen → Qwen VL decides → move the mouse and type → repeat.

The point is not to solve the problems well. The point is to see **where it gets stuck**.



[ Motivation Figure ]

<img width="1640" height="585" alt="image" src="https://github.com/user-attachments/assets/c9da230a-5a1c-47b6-a7f4-15868e71682f" />








<img width="384" height="204" alt="image" src="https://github.com/user-attachments/assets/9314c17e-6d43-4626-90cd-12b0f8cdabe8" />


---

## Two versions

### simple.py — drives your own browser (main)

```bash
pip install mss pyautogui pillow openai
# open the exam page in your browser yourself, log in
python simple.py
```

Starts after 3 seconds. It moves your actual mouse.
**To stop it, shove the mouse into the top-left corner of the screen** (pyautogui failsafe).

The environment is identical to a real candidate's. The tradeoff is that you
can't use the computer while it runs.

### agent.py — Playwright version

```bash
pip install -r requirements.txt && playwright install chromium
export CTA_URL="https://your-platform/problem/1"
CTA_MODE=examinee  python agent.py   # candidate mode
CTA_MODE=inspector python agent.py   # inspector mode
```

Launches its own browser window, so it can run in the background.
Automatically collects signals like "clicked but nothing on screen changed."
If login is required, run `python save_login.py` first, then set
`CTA_STORAGE_STATE=auth.json`.

---

## Pointing it at a model

All three are the same code. Only `BASE_URL` differs.

```python
BASE_URL = "http://localhost:8000/v1"      # local GPU
BASE_URL = "https://xxxx.ngrok.io/v1"      # Colab + tunnel
BASE_URL = "https://openrouter.ai/api/v1"  # hosted API
```

Local serving:

```bash
vllm serve Qwen/Qwen3-VL-8B-Instruct \
  --max-model-len 32768 \
  --limit-mm-per-prompt image=4 \
  --gpu-memory-utilization 0.90
```

---

## The two modes (personas.py)

|  | Candidate mode | Inspector mode |
|---|---|---|
| Goal | Solve the problems | Verify the problems |
| Finds | UI friction, discoverability | Missing or broken content |
| Verdict | Needs interpretation | Self-contained |
| Languages | One is enough | Must run all of them |

**Candidate mode is given no list of features.** The moment you hand it a list,
it just clicks through them in order and the wandering — which is the entire
output — disappears. Words like "inspect," "verify," and "bug" are kept out of
the prompt for the same reason.

**Inspector mode has no source of truth.** It judges only by contradictions
visible on screen. The problem statement *is* the spec. The strongest technique
here is cross-language differential testing: solve the same problem in every
allowed language and submit each one. The spec is identical, so the results
should be too. If one language times out or fails to compile, that alone is a
bug — no correct answer required.

---

## What to check on the first run

Open `shots/` and see whether the red crosshair lands on the button it meant to press.

- Roughly on target → just let it run the full 30 minutes
- **Always clustered near the top-left** → the model is emitting normalized
  0–1000 coordinates. Fix the coordinate conversion in `simple.py`, or set
  `CTA_COORD_MODE=normalized_1000` for `agent.py`
- Off in some other pattern → check capture resolution and viewport settings

---

## What to realistically expect

It will get through one or two problems in 30 minutes. Clicks miss often, and
when it gets stuck it tends to hammer the same spot. That is not a failure —
if it spends 20 minutes on problem 1 and confuses `Run` with `Test` along the
way, that confusion is the finding.

**Separate model limitations from UI defects:**

| Observation | Reading |
|---|---|
| Found the button, missed by a few px | Model limitation. Discard |
| Wandered without reading the statement | Model limitation. Discard |
| **Can see the buttons, doesn't know which one** | **UI problem. This is the finding** |
| Read the whole notice and still didn't know what to do | UI / notice problem |

---

## Files

```
simple.py      self-contained: screen capture + real mouse control
agent.py       Playwright main loop
personas.py    the two mode prompts — the heart of the experiment
prompts.py     assembles the per-mode system prompt
vision.py      smart_resize, coordinate inversion, overlay debugger
actions.py     click, type, dropdown, Monaco code insertion
model.py       Qwen client, context management, JSON parser
config.py      settings: viewport, session length, model
save_login.py  saves a logged-in session
```

---

## Not built yet

The session report. Right now you only get `trace.json` and `shots/`.
What's missing is something an inspector can actually read: each sticking point
with its screenshot, the agent's thinking at that moment, and how many steps it
burned there.

Worth feeding the trace to a separate model and having it write the report in
the third person — an agent recounting its own session tends to smooth things over.
