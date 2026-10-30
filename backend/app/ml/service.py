from typing import Any

from app.config import Settings
from app.ml.extraction import Gazetteer, build_extraction, load_gazetteer
from app.ml.provider import DisabledProvider, LlmProvider, build_provider
from app.ml.summary import summarise
from app.ml.triage import TriageModel

DEFAULT_FEATURES = (
    ("mlTriage", "Categorise and prioritise reports"),
    ("mlDuplicate", "Detect duplicate and related reports"),
    ("mlSummary", "Write incident summaries"),
    ("ocr", "Read invoices"),
    ("slaRisk", "Warn early about SLA risk"),
)


class MlService:
    """The only door to AI. Every method has a rule-based path, so a workflow never depends on AI being up."""

    def __init__(self, db: Any, settings: Settings, provider: LlmProvider | None = None) -> None:
        self._db = db
        self._settings = settings
        self.model = TriageModel.load()
        self.provider: LlmProvider = provider or build_provider(settings.llm_provider, settings.gemini_api_key, settings.gemini_model, settings.llm_timeout_seconds)
        self._gazetteer: Gazetteer | None = None

    # ---- feature switches (edited on the AI and Integrations screen) -----------------------

    async def features(self) -> list[dict[str, Any]]:
        stored = await self._db["integrations"].find_one({"_id": "ai"})
        saved = {item["key"]: item["enabled"] for item in (stored or {}).get("features", [])}
        return [{"key": key, "label": label, "enabled": saved.get(key, True), "mode": "AI" if saved.get(key, True) else "RULES"} for key, label in DEFAULT_FEATURES]

    async def enabled(self, key: str) -> bool:
        return next((item["enabled"] for item in await self.features() if item["key"] == key), True)

    async def set_feature(self, key: str, enabled: bool) -> list[dict[str, Any]]:
        if key not in {feature for feature, _ in DEFAULT_FEATURES}:
            raise KeyError(key)
        features = [{"key": item["key"], "label": item["label"], "enabled": enabled if item["key"] == key else item["enabled"]} for item in await self.features()]
        await self._db["integrations"].update_one({"_id": "ai"}, {"$set": {"features": features}}, upsert=True)
        return await self.features()

    @property
    def llm_ready(self) -> bool:
        return not isinstance(self.provider, DisabledProvider)

    # ---- the work ---------------------------------------------------------------------------

    async def gazetteer(self) -> Gazetteer:
        if self._gazetteer is None or not self._gazetteer.rooms:
            self._gazetteer = await load_gazetteer(self._db)
        return self._gazetteer

    def forget_gazetteer(self) -> None:
        self._gazetteer = None

    async def extract(self, text: str) -> dict[str, Any]:
        model = self.model if await self.enabled("mlTriage") else None
        return build_extraction(text, await self.gazetteer(), model)

    async def summarise(self, incident: dict[str, Any], reports: list[dict[str, Any]]) -> dict[str, Any]:
        use_llm = await self.enabled("mlSummary") and self.llm_ready
        return await summarise(self.provider, use_llm, incident, reports)
