import logfire 

from nemoguardrails import RailsConfig, LLMRails
from app.config import settings


_rails : LLMRails | None = None

def initialize_rails() -> None:
    """
    Build the NeMo Guardrails singleton at app startup.
    NeMo is used only as an input safety gate.

    """

    global _rails

    config = RailsConfig.from_path("app/guardrails/config")

    _rails = LLMRails(config)

    logfire.info("🛡️ NeMo Guardrails initialised.")



def guard(message: str) -> tuple[bool, str | None]:
    """
    Run a user message through the NeMo input rail.

    Returns:
        (True, response)  -> guardrail blocked the request.
        (False, None)     -> request passed and can continue to LangGraph.
    """
    if _rails is None:
        logfire.warning("⚠️ Guardrails not initialised — skipping gate.")
        return False, None

    with logfire.span("🛡️ Guardrails Check"):
        result = _rails.generate(messages=[{"role": "user", "content": message}])

        # NeMo returns {'role': 'assistant', 'content': '...'} — extract text
        content = ""

        if isinstance(result, dict):
            content = result.get("content", "") or ""

        if content:
            logfire.info(
                f"🛡️ Guardrails fired | query='{message[:80]}'"
            )
            return True, content

        logfire.info("✅ Guardrails passed.")
        return False, None