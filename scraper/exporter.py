"""CSV export — UTF-8-SIG so Thai text opens correctly in Excel on Windows."""
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import CSV_ENCODING, CSV_FILENAME_PREFIX
from paths import get_default_export_dir

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "facebook_name",
    "employee_id",
    "employee_name",
    "raw_comment",
    "comment_timestamp",
]


class ExportError(Exception):
    """Raised when the CSV cannot be written (e.g. file open elsewhere)."""


class CsvExporter:
    def __init__(self, export_dir: Path | None = None):
        self.export_dir = export_dir or get_default_export_dir()

    def export(self, records: list[dict]) -> Path:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{CSV_FILENAME_PREFIX}_{datetime.now():%Y%m%d_%H%M%S}.csv"
        filepath = self.export_dir / filename

        df = pd.DataFrame(records, columns=CSV_COLUMNS)
        # employee_id must stay a string — pandas would otherwise coerce/strip
        # any theoretical leading zero from the 8-digit ID.
        if "employee_id" in df.columns:
            df["employee_id"] = df["employee_id"].astype(str)

        try:
            df.to_csv(filepath, index=False, encoding=CSV_ENCODING)
        except (PermissionError, OSError) as exc:
            logger.exception("CSV export failed")
            raise ExportError(str(exc)) from exc

        logger.info("Exported %d records to %s", len(records), filepath)
        return filepath
