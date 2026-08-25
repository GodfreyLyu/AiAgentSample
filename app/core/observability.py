import logging

import logfire

from app.core.config import Settings

_configured = False


def configure_observability(settings: Settings) -> None:
    """Configure standard logging and Pydantic AI instrumentation once per process."""
    global _configured
    if _configured:
        return

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logfire.configure(send_to_logfire=settings.logfire_send_to_logfire)
    logfire.instrument_pydantic_ai()
    _configured = True

