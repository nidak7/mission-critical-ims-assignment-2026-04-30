from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCENARIO = ROOT / "outage_scenario.json"
API_URL = "http://localhost:8000/api/signals"


def post(payload: dict) -> None:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        print(response.read().decode("utf-8"))


def main() -> None:
    delay = float(sys.argv[1]) if len(sys.argv) > 1 else 0.6
    scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))
    for payload in scenario:
        post(payload)
        time.sleep(delay)


if __name__ == "__main__":
    main()
