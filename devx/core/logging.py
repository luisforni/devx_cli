import logging
from typing import Optional
from rich.logging import RichHandler

_CONFIGURED = False

def setup(level: str = "INFO") -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True)],
        )
        _CONFIGURED = True
    return logging.getLogger("devx")

def get_logger(name: Optional[str] = None) -> logging.Logger:
    if not _CONFIGURED:
        setup()
    return logging.getLogger(name or "devx")
