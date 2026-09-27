"""Inbox watcher: import anything a human drops into `./incoming`.

This is the "legitimate automation" middle path: a person views a page in their
own browser (satisfying any bot check as a human would) and saves it, or a small
bookmarklet POSTs the page you are looking at to the local API. The watcher then
picks the files up automatically — no crawling of a host that denies crawlers.

Files are routed through the same `import_files.import_text` path, so parsing,
entity resolution, flagging and idempotency all behave identically.

Layout::

    incoming/                <- drop .csv / .html files here
    incoming/processed/      <- successfully imported, moved aside
    incoming/failed/         <- unreadable/no rows, kept for inspection
"""
from __future__ import annotations

import argparse
import logging
import shutil
import time
from pathlib import Path

from app.db import SessionLocal
from pipeline.import_files import import_text

logger = logging.getLogger(__name__)

DEFAULT_INBOX = Path("incoming")
WATCHED_SUFFIXES = {".csv", ".html", ".htm", ".txt"}


def _classify_import(result: dict) -> bool:
    """True when the file produced something useful."""
    for key in ("races_created", "races_updated", "results_written"):
        if result.get(key):
            return True
    return False


def stage_inbox(inbox: Path | None = None) -> dict:
    """Import every pending file in the inbox once (used by the CLI and tests)."""
    inbox = Path(inbox or DEFAULT_INBOX)
    inbox.mkdir(parents=True, exist_ok=True)
    processed_dir = inbox / "processed"
    failed_dir = inbox / "failed"
    processed_dir.mkdir(exist_ok=True)
    failed_dir.mkdir(exist_ok=True)

    imported, failed, skipped = [], [], []
    db = SessionLocal()
    try:
        for path in sorted(inbox.iterdir()):
            if not path.is_file() or path.suffix.lower() not in WATCHED_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                shutil.move(str(path), failed_dir / path.name)
                failed.append({"file": path.name, "error": "empty file"})
                continue
            try:
                result = import_text(db, text, kind="auto", label=path.name)
            except Exception as exc:  # noqa: BLE001 — a bad file must not kill the loop
                logger.exception("inbox import failed for %s", path.name)
                shutil.move(str(path), failed_dir / path.name)
                failed.append({"file": path.name, "error": str(exc)[:200]})
                continue

            if _classify_import(result):
                shutil.move(str(path), processed_dir / path.name)
                imported.append({"file": path.name, **result})
            else:
                # keep it out of the way but flagged for a human to look at
                shutil.move(str(path), failed_dir / path.name)
                skipped.append({"file": path.name, "warnings": result.get("warnings", []),
                                "kind": result.get("kind")})
    finally:
        db.close()

    return {"imported": imported, "failed": failed, "skipped": skipped,
            "counts": {"imported": len(imported), "failed": len(failed),
                       "skipped": len(skipped)}}


def watch_forever(inbox: Path | None = None, interval: float = 15.0) -> None:
    logger.info("watching %s every %ss (Ctrl+C to stop)", inbox or DEFAULT_INBOX, interval)
    while True:
        summary = stage_inbox(inbox)
        if summary["counts"]["imported"]:
            logger.info("imported: %s", summary["counts"])
        time.sleep(interval)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Import files dropped into the inbox folder.")
    parser.add_argument("--inbox", default=None, help="folder to watch (default: ./incoming)")
    parser.add_argument("--once", action="store_true", help="scan once and exit")
    parser.add_argument("--interval", type=float, default=15.0, help="poll seconds")
    args = parser.parse_args(argv)

    inbox = Path(args.inbox) if args.inbox else None
    if args.once:
        print(stage_inbox(inbox))
    else:
        watch_forever(inbox, args.interval)


if __name__ == "__main__":
    main()
