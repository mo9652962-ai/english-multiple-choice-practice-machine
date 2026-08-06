from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.database import connect, initialize_database
from backend.app.services.docx_parser import import_exam_folder


def main() -> None:
    parser = argparse.ArgumentParser(description="批量导入考研英语一真题")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--draft-only", action="store_true")
    args = parser.parse_args()

    initialize_database()
    with connect() as connection:
        result = import_exam_folder(
            connection,
            args.folder.resolve(),
            publish_valid=not args.draft_only,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
