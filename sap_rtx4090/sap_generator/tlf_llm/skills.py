"""Skill loader — discovers and loads INSTRUCTIONS.md files for TLF domains.

Each domain has an INSTRUCTIONS.md with YAML frontmatter (metadata) and a body
containing domain knowledge, mandatory items, and output format guidance.
"""

import logging
import re
from pathlib import Path
from typing import Optional

import yaml

from .reference_library import StudyProfile

logger = logging.getLogger(__name__)

_INSTRUCTIONS_DIR = Path(__file__).parent / "instructions"

# Ordered list of domains — generation proceeds in this order
DOMAIN_ORDER = [
    "disposition",
    "demographics",
    "primary-efficacy",
    "secondary-efficacy",
    "safety-adverse-events",
    "safety-exposure",
    "safety-labs",
    "safety-vitals",
    "safety-ecg",
    "pk",
    "immunogenicity",
    "qol",
    "listings",
]


class SkillLoader:
    """Loads and caches INSTRUCTIONS.md files for TLF domains."""

    _instance: Optional["SkillLoader"] = None

    def __init__(self, instructions_dir: Path = _INSTRUCTIONS_DIR):
        self.instructions_dir = instructions_dir
        self._cache: dict[str, dict] = {}  # domain → {"meta": {...}, "body": "..."}
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "SkillLoader":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_all(self) -> None:
        """Discover and parse all INSTRUCTIONS.md files."""
        if self._loaded:
            return

        for domain in DOMAIN_ORDER:
            fpath = self.instructions_dir / domain / "INSTRUCTIONS.md"
            if not fpath.exists():
                logger.warning(f"Missing INSTRUCTIONS.md for domain: {domain}")
                continue

            text = fpath.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(text)
            self._cache[domain] = {"meta": meta, "body": body}

        self._loaded = True
        logger.info(f"Loaded {len(self._cache)} domain instruction files")

    def load_skill(self, domain: str) -> str:
        """Return the instruction body for a domain (without frontmatter)."""
        self._load_all()
        entry = self._cache.get(domain)
        if not entry:
            logger.warning(f"No instructions found for domain: {domain}")
            return ""
        return entry["body"]

    def get_metadata(self, domain: str) -> dict:
        """Return the frontmatter metadata for a domain."""
        self._load_all()
        entry = self._cache.get(domain)
        return entry["meta"] if entry else {}

    def should_run(self, domain: str, profile: StudyProfile) -> bool:
        """Check whether a domain should run for this study profile.

        Always returns True — every domain runs. The LLM instructions
        already say "this domain only runs when the protocol includes X"
        so the LLM will return an empty list if the domain doesn't apply.
        This avoids missing domains due to metadata extraction errors.
        """
        self._load_all()
        return True

    def get_domain_order(self) -> list[str]:
        """Return the ordered list of domains."""
        return list(DOMAIN_ORDER)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a markdown file into YAML frontmatter dict and body string."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text

    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        meta = {}

    body = match.group(2).strip()
    return meta, body
