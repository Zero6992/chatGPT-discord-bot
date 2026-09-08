"""Deterministic executable fixture, launched through the production subprocess code."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

mode = os.environ.get("FIXTURE_MODE", "claude")
if mode == "hang":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    Path(os.environ["PID_FILE"]).write_text(str(child.pid))
    time.sleep(120)
if mode == "overflow":
    sys.stdout.write("x" * 100000)
    sys.stdout.flush()
    time.sleep(120)
if mode == "bad":
    print("private secret diagnostic", file=sys.stderr)
    print("invalid JSON")
    sys.exit(2)
prompt = sys.stdin.read()
if mode == "echo":
    print(json.dumps({"argv": sys.argv[1:], "prompt": prompt, "env": sorted(os.environ)}))
    sys.exit(0)
session = "a430c365-ec1b-479f-9a8d-647fd4cdb8a9"
if "--resume" in sys.argv:
    session = sys.argv[sys.argv.index("--resume") + 1]
elif "resume" in sys.argv:
    session = sys.argv[sys.argv.index("resume") + 1]
if mode == "codex":
    for event in [
        {"type": "thread.started", "thread_id": session},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "item_1", "type": "agent_message", "text": "CLI answer"},
        },
        {"type": "turn.completed", "usage": {"input_tokens": 8, "output_tokens": 2}},
    ]:
        print(json.dumps(event))
else:
    print(
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "stop_reason": "end_turn",
                "result": "CLI answer",
                "session_id": session,
            }
        )
    )
