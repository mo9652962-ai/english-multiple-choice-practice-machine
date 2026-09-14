#!/usr/bin/env python3
"""Deprecated release entrypoint kept as a safe compatibility notice.

The former implementation performed an unreviewed local build, signed with a
developer self-signed certificate, assembled a debug APK, and uploaded directly
to GitHub. That path could bypass the repository's content provenance,
signature, artifact, and runtime gates.

Use the protected GitHub workflows instead:

* ``.github/workflows/ci.yml`` for pull-request and branch verification;
* ``.github/workflows/release.yml`` for the Windows tagged release;
* ``.github/workflows/android.yml`` for the Android build and emulator evidence.

This compatibility entrypoint intentionally performs no build, signing,
upload, or release mutation.
"""

from __future__ import annotations

import sys


MESSAGE = (
    "scripts/release_all.py is disabled: the legacy one-click release path "
    "could bypass provenance, formal signing, Android runtime, and artifact "
    "gates. Use the protected GitHub Actions release workflows instead."
)


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
