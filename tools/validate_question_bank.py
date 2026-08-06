from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.esq import EsqValidationError, load_esq_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an ESQ 1.0 question bank")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        package = load_esq_package(args.path)
    except EsqValidationError as error:
        print(
            json.dumps(
                {"valid": False, "errors": error.details},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    totals = {
        "papers": len(package["papers"]),
        "units": sum(len(paper["units"]) for paper in package["papers"]),
        "questions": sum(
            len(unit["questions"])
            for paper in package["papers"]
            for unit in paper["units"]
        ),
        "assets": len(package.get("assets", {})),
    }
    print(
        json.dumps(
            {
                "valid": True,
                "packageId": package["manifest"]["packageId"],
                "contentVersion": package["manifest"]["contentVersion"],
                "totals": totals,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
