from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

from prosperity.llm.budget import BudgetTracker
from prosperity.llm.caching import PromptCache
from prosperity.llm.json_io import extract_json_object
from prosperity.settings import AppSettings


class LLMClient:
    def __init__(self, settings: AppSettings, cache_root: Path):
        self.settings = settings
        self.cache = PromptCache(cache_root / "llm")
        self.budget = BudgetTracker(cache_root / "llm_budget.json", settings.llm.daily_budget_usd)

    def generate_json(self, role: str, prompt: str, model: str | None = None) -> dict[str, Any]:
        selected_model = model or self.settings.llm.strategist_model
        key = json.dumps({"role": role, "model": selected_model, "prompt": prompt}, sort_keys=True)
        cached = self.cache.get(key)
        if cached is not None:
            return extract_json_object(cached)
        if not self.settings.llm.allow_live_requests or not self.settings.openai_api_key:
            raise RuntimeError("Live LLM requests are disabled. Use heuristic generators or enable config.")
        response = self._call_openai(prompt, selected_model)
        self.cache.set(key, response)
        return extract_json_object(response)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def _call_openai(self, prompt: str, model: str) -> str:
        if not self.budget.can_spend(0.02):
            raise RuntimeError("Daily LLM budget exhausted")
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.responses.create(
            model=model,
            input=prompt,
        )
        self.budget.record(0.02, role="generic", model=model)
        return response.output_text
