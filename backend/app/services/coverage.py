"""生词覆盖率统计——v9.28 Gemini batch5 任务2 落地

「您已覆盖本篇文章 85% 的词汇」：
  coverage = |文章词汇 ∩ 用户已掌握词库| / |文章词汇|
纯 Python 分词 + 极简词形还原（不引 nltk）；文章 ~6k 字分词 <10ms，现算无需缓存。
"""
import re
import sqlite3

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "are", "was", "were", "be", "been", "being",
    "it", "this", "that", "these", "those", "i", "you", "he", "she",
    "we", "they", "my", "your", "his", "her", "our", "their",
    "as", "by", "from", "into", "about", "than", "so", "if", "then",
    "not", "no", "will", "would", "can", "could", "should", "have", "has",
    "had", "do", "does", "did", "there", "here", "which", "who", "whom",
    "what", "when", "where", "why", "how", "all", "any", "some", "more",
    "most", "other", "such", "only", "own", "same", "too", "very", "just",
}

_TOKEN_RE = re.compile(r"\b[a-zA-Z]+\b")


def _lemmatize(word: str) -> str:
    """极简词形还原：ies→y、复数去 s、ing/ed 剥离（保守——不破坏词干）"""
    w = word
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ing") and len(w) > 5:
        return w[:-3]
    if w.endswith("ed") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def tokenize_passage(text: str) -> set[str]:
    """文章 → 去重基础词汇集（分词 + 去停用词 + 词形还原）"""
    words = _TOKEN_RE.findall(text.lower())
    out: set[str] = set()
    for w in words:
        if w in STOP_WORDS or len(w) < 2:
            continue
        out.add(_lemmatize(w))
    return out


def get_passage_coverage(
    connection: sqlite3.Connection,
    unit_id: int,
    user_id: int | None = None,
) -> dict:
    """单篇文章覆盖率：文章词汇 ∩ 用户词库（mastered/learning）"""
    row = connection.execute(
        "SELECT passage FROM units WHERE id = ?", (unit_id,)
    ).fetchone()
    if not row or not row["passage"]:
        return {"unit_id": unit_id, "coverage": None, "total_words": 0, "known_words": 0}

    passage_vocab = tokenize_passage(row["passage"])
    if not passage_vocab:
        return {"unit_id": unit_id, "coverage": None, "total_words": 0, "known_words": 0}

    # 用户词库（mastered/learning 视为已掌握；raw/new 不算）
    known: set[str] = set()
    for term, lemma, status in connection.execute(
        """SELECT term, lemma, study_status FROM vocabulary_entries
           WHERE user_id IS ? AND study_status IN ('mastered', 'learning')""",
        (user_id,),
    ).fetchall():
        known.add((term or "").lower())
        if lemma:
            known.add(lemma.lower())

    known_words = passage_vocab & known
    coverage = round(len(known_words) * 100.0 / len(passage_vocab), 1)
    return {
        "unit_id": unit_id,
        "coverage": coverage,
        "total_words": len(passage_vocab),
        "known_words": len(known_words),
    }
