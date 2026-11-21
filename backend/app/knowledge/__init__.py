"""Per-account company knowledge: what the owner told us about the business, as Markdown.

Each account keeps its file at `app/knowledge/<account id>/company_knowledge.md`.
"""

import re
from functools import lru_cache
from pathlib import Path

KNOWLEDGE_DIRECTORY = Path(__file__).resolve().parent
KNOWLEDGE_FILE_NAME = "company_knowledge.md"


@lru_cache
def load_company_knowledge(account_id: str) -> str:
    """Read the company knowledge of one account.

    Args:
        account_id: The account id, which is also the name of its knowledge folder.

    Returns:
        The Markdown text without surrounding whitespace, or an empty string when the account has no
        knowledge file (or the id is not a plain folder name).
    """
    if not re.fullmatch(r"[a-z0-9_-]+", account_id):
        return ""
    knowledge_path = KNOWLEDGE_DIRECTORY / account_id / KNOWLEDGE_FILE_NAME
    if not knowledge_path.is_file():
        return ""
    return knowledge_path.read_text(encoding="utf-8").strip()
