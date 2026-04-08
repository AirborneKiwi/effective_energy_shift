from __future__ import annotations

import logging
import sys

class LoggingObserver:
    """Basic observer that logs the state to the console or a logger."""

    def __init__(
        self,
        logger: logging.Logger | None = None,
        level: int = logging.INFO,
        stream=None,
    ) -> None:
        self._logger = logger or logging.getLogger("efes_core")
        self._logger.setLevel(level)
        self._logger.propagate = False

        if not self._logger.handlers:
            handler = logging.StreamHandler(stream or sys.stdout)
            handler.setLevel(level)
            handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
            self._logger.addHandler(handler)

    def on_step(self, obj: Any) -> bool:
        self._logger.info("%s",   obj    )
        return False
