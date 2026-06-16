"""Entry point for TOA Lucky Draw Collector."""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import config
import paths


def setup_logging() -> None:
    logs_dir = paths.get_logs_dir()
    handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    if not getattr(sys, "frozen", False):
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(stream)


def setup_playwright_browsers_path() -> None:
    """Point Playwright at the sibling ms-playwright folder shipped with the onedir build."""
    browsers_dir = paths.get_browsers_dir()
    if browsers_dir.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir)


def main() -> None:
    setup_logging()
    setup_playwright_browsers_path()
    logging.getLogger(__name__).info("Starting %s", config.APP_NAME)

    from ui.app import CollectorApp

    app = CollectorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
