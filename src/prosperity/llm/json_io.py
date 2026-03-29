from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(text: str) -> dict[str, Any]:
    fenced = re.search(r"```json\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    payload = fenced.group(1) if fenced else text.strip()
    return json.loads(payload)
