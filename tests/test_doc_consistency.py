"""Guards the numbers and versions the documentation quotes against the real data.

This repo states concrete figures in a lot of places — word counts, paper counts,
per-category vocabulary splits, the release version, the frontend/backend version
mirrors. They had already drifted:

  * README claimed 7,958 vocabulary words; the shipped seed database has 7,959.
  * The 六级 category was documented as 1,304; it is 1,305.
  * README claimed the vocabulary includes "双语例句"; ``vocabulary_examples``
    is an empty table, so that claim was not supported by the data at all.
  * The public landing page and docs/llms*.txt still advertised v2.1.3 while
    VERSION, both package.json files and the Electron build were on 2.2.0.

Every assertion below re-derives the number from its source of truth, so the docs
cannot silently drift again.
"""

from __future__ import annotations

import json
import re
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_DB = ROOT / "frontend" / "public" / "question_bank.db"

# Docs that quote the shipped content figures.
CONTENT_DOCS = ["README.md", "README.en.md", "llms.txt"]

# Historical release-evidence records legitimately name older versions, so they
# are excluded from the "live docs" version check.
LIVE_DOCS = [
    "README.md",
    "README.en.md",
    "llms.txt",
    "docs/index.html",
    "docs/landing-3d-concept.html",
    "docs/llms.txt",
    "docs/llms-full.txt",
]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _seed_counts() -> dict[str, int]:
    """Read the shipped seed database — the only source of truth for content."""
    if not SEED_DB.exists():
        raise unittest.SkipTest(f"seed database not present: {SEED_DB}")
    connection = sqlite3.connect(SEED_DB)
    try:
        counts = {}
        for table in ("papers", "questions", "vocabulary_entries"):
            counts[table] = connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
        counts["phonetic"] = connection.execute(
            "SELECT COUNT(*) FROM vocabulary_entries "
            "WHERE TRIM(COALESCE(phonetic, '')) <> ''"
        ).fetchone()[0]
        counts["vocabulary_examples"] = connection.execute(
            "SELECT COUNT(*) FROM vocabulary_examples"
        ).fetchone()[0]
        categories = [
            row[0] or ""
            for row in connection.execute("SELECT category FROM vocabulary_entries")
        ]
        for key in ("高中", "四级", "六级", "考研"):
            # A word counts toward a category when it is the primary tag.
            counts[f"cat_{key}"] = sum(
                1 for c in categories if c.split("|")[0].split("·")[0] == key
            )
        return counts
    finally:
        connection.close()


def _version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


class VersionConsistencyTests(unittest.TestCase):
    def test_version_file_is_semver(self) -> None:
        self.assertRegex(_version(), r"^\d+\.\d+\.\d+$")

    def test_package_json_mirrors_match_version(self) -> None:
        version = _version()
        for name in (
            "frontend/package.json",
            "frontend/package-lock.json",
            "electron/package.json",
            "electron/package-lock.json",
        ):
            payload = json.loads(_read(name))
            self.assertEqual(
                payload.get("version"),
                version,
                f"{name} version {payload.get('version')!r} != VERSION {version!r}",
            )

    def test_shared_release_metadata_matches_version(self) -> None:
        payload = json.loads(_read("frontend/public/release-metadata.json"))
        self.assertEqual(payload["metadata"]["version"], _version())

    def test_live_docs_advertise_the_current_version(self) -> None:
        """A public page that says 'current release' must not name an old one."""
        version = _version()
        for name in LIVE_DOCS:
            text = _read(name)
            self.assertIn(
                version,
                text,
                f"{name} never mentions the current version {version}",
            )
            stale = set(re.findall(r"\bv(2\.1\.\d+)\b", text))
            self.assertFalse(
                stale,
                f"{name} still advertises stale version(s) {sorted(stale)} "
                f"while VERSION is {version}",
            )

    def test_landing_page_structured_data_matches_version(self) -> None:
        """The JSON-LD softwareVersion is machine-read; keep it honest."""
        text = _read("docs/index.html")
        found = re.findall(r'"softwareVersion":\s*"([^"]+)"', text)
        self.assertTrue(found, "docs/index.html has no softwareVersion in JSON-LD")
        for value in found:
            self.assertEqual(value, _version())


class ContentCountTests(unittest.TestCase):
    """Every content figure in the docs must match the shipped seed database."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.counts = _seed_counts()

    def test_docs_state_the_real_vocabulary_total(self) -> None:
        total = self.counts["vocabulary_entries"]
        # Compare digit-only to be immune to 7,959 vs 7959 formatting.
        for name in CONTENT_DOCS:
            text = _read(name).replace(",", "")
            self.assertIn(
                str(total),
                text,
                f"{name} never states the real vocabulary total ({total})",
            )

    def test_docs_do_not_state_a_stale_vocabulary_total(self) -> None:
        """The headline vocabulary total must be the real one.

        Only total claims are checked. Subset figures are legitimate and must not
        be caught: '7,951 词带音标' (phonetic coverage) and the roadmap's
        historical '7,751 词' both describe something other than the total.
        """
        total = self.counts["vocabulary_entries"]
        # Phrasings that assert the whole vocabulary size.
        total_claim = re.compile(
            r"(?:内置|included|bundled)?\s*([\d,]{4,7})\s*个?\s*"
            r"(?:全类别核心)?词汇|"
            r"([\d,]{4,7})-word vocabulary",
        )
        for name in CONTENT_DOCS:
            text = _read(name)
            for match in total_claim.finditer(text):
                raw = match.group(1) or match.group(2)
                value = int(raw.replace(",", ""))
                self.assertEqual(
                    value,
                    total,
                    f"{name} claims a vocabulary total of {value} but the seed DB has {total}",
                )

    def test_roadmap_historical_counts_are_not_treated_as_current(self) -> None:
        """Guard the exclusion above: the stale count must live in the roadmap."""
        readme = _read("README.md").replace(",", "")
        if "7751" not in readme:
            self.skipTest("no historical vocabulary figure recorded")
        line = next(
            l for l in readme.splitlines() if "7751" in l
        )
        self.assertRegex(
            line,
            r"v\d+\.\d+\.\d+-beta|^\s*-\s*\[x\]",
            "a historical vocabulary count appears outside a changelog line",
        )

    def test_per_category_splits_match_the_database(self) -> None:
        """The '高中 666 / 四级 825 / 六级 N / 考研 M' breakdown must be exact."""
        readme = _read("README.md").replace(",", "")
        for key in ("高中", "四级", "六级", "考研"):
            expected = self.counts[f"cat_{key}"]
            self.assertIn(
                f"{key} {expected}",
                readme,
                f"README.md does not state {key} = {expected} (real count)",
            )

    def test_docs_state_the_real_paper_and_question_counts(self) -> None:
        """Papers/questions are stated in Chinese and English phrasings."""
        papers = self.counts["papers"]
        questions = self.counts["questions"]
        for name in CONTENT_DOCS:
            text = _read(name)
            self.assertIn(
                str(papers),
                text,
                f"{name} never states the real paper count ({papers})",
            )
            self.assertIn(
                str(questions),
                text,
                f"{name} never states the real question count ({questions})",
            )
            # The specific phrasings the READMEs use, so a wrong number with the
            # right unit is caught rather than passing on a bare digit match.
            # Only "bundled content" claims are checked — unrelated uses such as
            # '只生成第 1 套草稿' (import behaviour) and 'one passage + 20
            # questions' (cloze format) must not be caught.
            for pattern, expected in (
                (r"内置\s*(\d+)\s*套", papers),
                (r"(\d+)\s*(?:bundled )?(?:AI-simulated )?papers?", papers),
                (r"(\d+)\s*(?:objective|客观)题", questions),
                (r"(\d+)\s*objective questions?", questions),
            ):
                for found in re.findall(pattern, text):
                    self.assertEqual(
                        int(found),
                        expected,
                        f"{name} states {found} for {pattern!r} but the seed DB has {expected}",
                    )

    def test_bilingual_example_claims_match_the_data(self) -> None:
        """Do not advertise examples the shipped database does not contain.

        ``vocabulary_examples`` is a real table with a real importer, but the
        bundled seed ships zero rows. Describing the *capability* (a table plus
        importer that fills from licensed corpora) is accurate; claiming the
        bundled data already contains them is not.
        """
        if self.counts["vocabulary_examples"] > 0:
            self.skipTest("seed database now ships vocabulary examples")

        # A claim is misleading when it presents examples as already-bundled
        # content. '随授权语料导入' / 'source-aware' phrasings are capability
        # descriptions and are fine.
        bundled_claim = re.compile(
            r"(?:内置|bundled|当前|included)[^。.\n]{0,20}(?:双语例句|bilingual example)"
            r"|(?:双语例句|bilingual example)[^。.\n]{0,10}(?:已内置|已包含|bundled)"
        )
        for name in CONTENT_DOCS:
            text = _read(name)
            for match in bundled_claim.finditer(text):
                line = text[: match.start()].count("\n") + 1
                self.fail(
                    f"{name}:{line} presents bilingual examples as bundled content "
                    f"but the seed database has 0 rows: {match.group(0)!r}"
                )


class ReleaseGateConsistencyTests(unittest.TestCase):
    """The release workflow's vocabulary floor must match the shipped data."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.counts = _seed_counts()

    def test_release_workflow_min_vocabulary_matches_seed(self) -> None:
        text = _read(".github/workflows/release.yml")
        floors = {int(m) for m in re.findall(r"--min-vocabulary\s+(\d+)", text)}
        self.assertTrue(floors, "release.yml sets no --min-vocabulary floor")
        total = self.counts["vocabulary_entries"]
        for floor in floors:
            self.assertEqual(
                floor,
                total,
                f"release.yml --min-vocabulary {floor} != shipped vocabulary {total}",
            )

    def test_release_script_in_readme_matches_seed(self) -> None:
        text = _read("README.md")
        floors = {int(m) for m in re.findall(r"-MinVocabulary\s+(\d+)", text)}
        total = self.counts["vocabulary_entries"]
        for floor in floors:
            self.assertEqual(
                floor,
                total,
                f"README -MinVocabulary {floor} != shipped vocabulary {total}",
            )


if __name__ == "__main__":
    unittest.main()
