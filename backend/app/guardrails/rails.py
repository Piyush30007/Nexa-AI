import asyncio
import concurrent.futures
import logfire 

from nemoguardrails import RailsConfig, LLMRails
from app.config import settings


_rails : LLMRails | None = None

OUTPUT_FALLBACK_MESSAGE = (
    "I cannot provide this response because it contains unverified or sensitive information. "
    "Please refer to official company policy documentation."
)


def initialize_rails() -> None:
    """
    Build the NeMo Guardrails singleton at app startup.
    NeMo is used for input safety and output safety action dispatching.
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


def _run_coroutine_sync(coro):
    """Helper to execute an async coroutine synchronously."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return loop.run_until_complete(coro)


def guard_output(
    response_text: str,
    context: dict | None = None
) -> tuple[bool, str | None]:
    """
    Run generated assistant output through NeMo output guardrails action dispatcher.

    Returns:
        (False, None)             -> output passed
        (True, fallback_message) -> output blocked
    """
    if _rails is None:
        logfire.warning("⚠️ Guardrails not initialised — skipping output gate.")
        return False, None

    with logfire.span("🛡️ Output Guardrails Check"):
        try:
            dispatcher = _rails.runtime.action_dispatcher
            coro = dispatcher.execute_action(
                "CheckBotResponseAction",
                {"output_text": response_text, "context": context or {}}
            )
            action_result, _status = _run_coroutine_sync(coro)
            is_safe = bool(action_result)
        except Exception as e:
            logfire.error(f"⚠️ Error executing output guardrails action: {e}")
            return True, OUTPUT_FALLBACK_MESSAGE

        if not is_safe:
            logfire.warning("🛡️ Output Guardrails blocked unsafe response")
            return True, OUTPUT_FALLBACK_MESSAGE

        logfire.info("✅ Output Guardrails passed.")
        return False, None