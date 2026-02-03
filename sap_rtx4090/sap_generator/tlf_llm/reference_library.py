"""Reference TLF Library — loads 50 extracted TLF JSONs and finds similar studies.

Each reference JSON contains:
  - study_facts: {therapeutic_area, phase, design_type, has_pk, ...}
  - tables: [{title, type, population, section, conditional}, ...]
  - figures: [...]
  - listings: [...]

Example matching uses an LLM call to select the 2-3 most similar studies
from the library based on the new protocol's metadata.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Path to the 50 reference TLF JSONs
_REFERENCE_DIR = (
    Path(__file__).parent.parent.parent
    / "reference_saps"
    / "_extracted"
    / "tlf_json"
)


@dataclass
class StudyProfile:
    """Metadata for a single study, used for matching."""

    nct_id: str
    therapeutic_area: str = ""
    phase: str = ""
    design_type: str = ""  # superiority, single_arm, non_inferiority, biosimilar, descriptive
    num_arms: int = 1
    has_pk: bool = False
    has_immunogenicity: bool = False
    has_qol: bool = False
    has_central_review: bool = False
    treatment_periods: list[str] = field(default_factory=list)


@dataclass
class ReferenceStudy:
    """A reference study with its full TLF lists."""

    profile: StudyProfile
    tables: list[dict] = field(default_factory=list)
    figures: list[dict] = field(default_factory=list)
    listings: list[dict] = field(default_factory=list)


@dataclass
class MatchedStudy:
    """A matched reference study with reasoning."""

    study: ReferenceStudy
    reasoning: str = ""


# Domain → table types mapping for filtering reference examples
DOMAIN_TYPE_MAP = {
    "disposition": ["disposition", "screening_failures"],
    "demographics": [
        "demographics", "baseline", "medical_history",
        "disease_characteristics",
    ],
    "primary-efficacy": [
        "efficacy_binary", "efficacy_continuous", "efficacy_tte",
        "subgroup",
    ],
    "secondary-efficacy": [
        "efficacy_binary", "efficacy_continuous", "efficacy_tte",
    ],
    "safety-adverse-events": [
        "ae_overview", "ae_by_soc_pt", "ae_serious", "ae_death",
        "ae_discontinuation", "ae_grade3plus", "aesi",
    ],
    "safety-exposure": ["exposure", "concomitant_medications"],
    "safety-labs-vitals": [
        "labs_summary", "labs_shift", "vitals", "ecg", "physical_exam",
    ],
    "pk": ["pk_parameters", "pk_concentration"],
    "immunogenicity": ["immunogenicity"],
    "qol": ["qol"],
    "listings": [],  # listings domain gets all listing entries
}

# Figure types per domain
DOMAIN_FIGURE_MAP = {
    "primary-efficacy": ["km_plot", "forest_plot", "waterfall_plot"],
    "secondary-efficacy": ["efficacy_continuous", "efficacy_binary"],
    "safety-labs-vitals": ["labs_summary"],
    "pk": ["pk_concentration"],
}


class ReferenceLibrary:
    """Manages the 50-study reference TLF library.

    Singleton — use get_instance() to access.
    """

    _instance: Optional["ReferenceLibrary"] = None
    _studies: dict[str, ReferenceStudy]  # nct_id → ReferenceStudy

    def __init__(self, reference_dir: Path = _REFERENCE_DIR):
        self.reference_dir = reference_dir
        self._studies = {}
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "ReferenceLibrary":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self) -> None:
        """Load all reference TLF JSONs."""
        if self._loaded:
            return

        json_files = sorted(self.reference_dir.glob("*.json"))
        for fpath in json_files:
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                facts = data.get("study_facts", {})
                nct_id = data.get("_nct", fpath.stem)

                profile = StudyProfile(
                    nct_id=nct_id,
                    therapeutic_area=facts.get("therapeutic_area", ""),
                    phase=facts.get("phase", ""),
                    design_type=facts.get("design_type", ""),
                    num_arms=facts.get("num_arms", 1),
                    has_pk=facts.get("has_pk", False),
                    has_immunogenicity=facts.get("has_immunogenicity", False),
                    has_qol=facts.get("has_qol", False),
                    has_central_review=facts.get("has_central_review", False),
                    treatment_periods=facts.get("treatment_periods", []),
                )

                self._studies[nct_id] = ReferenceStudy(
                    profile=profile,
                    tables=data.get("tables", []),
                    figures=data.get("figures", []),
                    listings=data.get("listings", []),
                )
            except Exception as e:
                logger.warning(f"Failed to load {fpath.name}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._studies)} reference TLF studies")

    def format_library_summary(self) -> str:
        """Compact text summary of all studies for the LLM matching prompt."""
        self.load()
        lines = []
        for nct_id, ref in sorted(self._studies.items()):
            p = ref.profile
            flags = []
            if p.has_pk:
                flags.append("pk")
            if p.has_immunogenicity:
                flags.append("immuno")
            if p.has_qol:
                flags.append("qol")
            flag_str = ", ".join(flags) if flags else "none"
            lines.append(
                f"- {nct_id}: {p.therapeutic_area}, {p.phase}, "
                f"{p.design_type}, {p.num_arms} arms, "
                f"assessments=[{flag_str}], "
                f"{len(ref.tables)} tables, {len(ref.figures)} figures, "
                f"{len(ref.listings)} listings"
            )
        return "\n".join(lines)

    async def find_similar(
        self,
        query: StudyProfile,
        top_k: int = 3,
        llm_caller=None,
    ) -> list[MatchedStudy]:
        """Use LLM to select the most similar reference studies.

        Args:
            query: The new protocol's study profile.
            top_k: Number of matches to return.
            llm_caller: Async function(system_prompt, user_message) -> str.
                        Injected by generator.py to avoid circular imports.

        Returns:
            List of MatchedStudy with reasoning.
        """
        self.load()

        if not self._studies:
            logger.warning("No reference studies loaded")
            return []

        if llm_caller is None:
            logger.warning("No LLM caller provided, returning empty matches")
            return []

        library_summary = self.format_library_summary()

        system_prompt = (
            "You are a clinical trial analyst selecting reference SAPs.\n\n"
            "Given a new protocol's characteristics, select 2-3 example studies "
            "from the library that are most similar and useful as TLF references.\n\n"
            "## Selection Strategy\n"
            "1. Prioritize matching therapeutic area and indication\n"
            "2. Match study design type (superiority, single_arm, biosimilar, etc.)\n"
            "3. Match phase and complexity (number of arms)\n"
            "4. Consider assessment overlap (PK, immunogenicity, QoL)\n\n"
            "## Output\n"
            "Return valid JSON:\n"
            '{"selected": ["NCT_ID_1", "NCT_ID_2"], '
            '"reasoning": "Brief explanation"}\n\n'
            f"Select up to {top_k} studies. If no good matches exist, return fewer."
        )

        query_json = json.dumps({
            "therapeutic_area": query.therapeutic_area,
            "phase": query.phase,
            "design_type": query.design_type,
            "num_arms": query.num_arms,
            "has_pk": query.has_pk,
            "has_immunogenicity": query.has_immunogenicity,
            "has_qol": query.has_qol,
            "treatment_periods": query.treatment_periods,
        }, indent=2)

        user_message = (
            f"## New Protocol Profile\n{query_json}\n\n"
            f"## Available Reference Studies\n{library_summary}\n\n"
            f"Select the {top_k} most similar studies."
        )

        try:
            response = await llm_caller(system_prompt, user_message)
            result = _parse_json_from_response(response)

            selected_ids = result.get("selected", [])
            reasoning = result.get("reasoning", "")

            matches = []
            for nct_id in selected_ids[:top_k]:
                if nct_id in self._studies:
                    matches.append(MatchedStudy(
                        study=self._studies[nct_id],
                        reasoning=reasoning,
                    ))
                else:
                    logger.warning(f"LLM selected unknown NCT ID: {nct_id}")

            logger.info(
                f"Matched {len(matches)} reference studies: "
                f"{[m.study.profile.nct_id for m in matches]}"
            )
            return matches

        except Exception as e:
            logger.error(f"Example matching failed: {e}")
            return []

    def get_domain_tlfs(self, nct_id: str, domain: str) -> dict:
        """Get a reference study's TLFs filtered to a specific domain.

        Returns dict with "tables", "figures", "listings" keys.
        """
        self.load()
        ref = self._studies.get(nct_id)
        if not ref:
            return {"tables": [], "figures": [], "listings": []}

        type_filter = set(DOMAIN_TYPE_MAP.get(domain, []))
        fig_filter = set(DOMAIN_FIGURE_MAP.get(domain, []))

        # For listings domain, return all listings (not filtered by type)
        if domain == "listings":
            return {
                "tables": [],
                "figures": [],
                "listings": ref.listings,
            }

        filtered_tables = [
            t for t in ref.tables if t.get("type", "") in type_filter
        ]
        filtered_figures = [
            f for f in ref.figures if f.get("type", "") in fig_filter
        ]

        return {
            "tables": filtered_tables,
            "figures": filtered_figures,
            "listings": [],
        }

    def format_domain_examples(
        self, matches: list[MatchedStudy], domain: str
    ) -> str:
        """Format matched studies' TLFs for a specific domain as prompt context."""
        if not matches:
            return "No reference examples available."

        parts = []
        for match in matches:
            nct_id = match.study.profile.nct_id
            p = match.study.profile
            domain_tlfs = self.get_domain_tlfs(nct_id, domain)

            tables = domain_tlfs["tables"]
            figures = domain_tlfs["figures"]
            listings = domain_tlfs["listings"]

            if not tables and not figures and not listings:
                continue

            header = (
                f"### {nct_id} ({p.therapeutic_area}, {p.phase}, "
                f"{p.design_type}, {p.num_arms} arms)"
            )

            lines = [header]
            if tables:
                lines.append("**Tables:**")
                for t in tables:
                    lines.append(
                        f"  - {t.get('title', 'Untitled')} "
                        f"[type={t.get('type', '?')}, "
                        f"pop={t.get('population', '?')}]"
                    )
            if figures:
                lines.append("**Figures:**")
                for f in figures:
                    lines.append(
                        f"  - {f.get('title', 'Untitled')} "
                        f"[type={f.get('type', '?')}, "
                        f"pop={f.get('population', '?')}]"
                    )
            if listings:
                lines.append("**Listings:**")
                for li in listings:
                    lines.append(
                        f"  - {li.get('title', 'Untitled')} "
                        f"[pop={li.get('population', '?')}]"
                    )

            parts.append("\n".join(lines))

        return "\n\n".join(parts) if parts else "No reference examples for this domain."


def _parse_json_from_response(response: str) -> dict:
    """Extract JSON from an LLM response that may contain markdown fences."""
    text = response.strip()

    # Try raw JSON first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code fence
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning(f"Could not parse JSON from response: {text[:200]}")
    return {}


def build_study_profile(extraction: dict) -> StudyProfile:
    """Build a StudyProfile from an extraction dict (from tlf_integration or metadata call).

    Handles both the full extraction schema (from SAP jobs) and a lightweight
    metadata-only dict.
    """
    study_design = extraction.get("study_design", {})
    assessments = extraction.get("assessments_collected", {})

    # Handle QoL — can be bool or list
    qol_val = assessments.get("qol", False)
    has_qol = bool(qol_val) if isinstance(qol_val, bool) else len(qol_val) > 0

    return StudyProfile(
        nct_id=extraction.get("nct_id", "UNKNOWN"),
        therapeutic_area=extraction.get("therapeutic_area", ""),
        phase=study_design.get("phase", ""),
        design_type=study_design.get("type", ""),
        num_arms=len(extraction.get("arms", [])) or 1,
        has_pk=assessments.get("pk", False),
        has_immunogenicity=assessments.get("immunogenicity", False),
        has_qol=has_qol,
        has_central_review=study_design.get("has_central_review", False),
        treatment_periods=extraction.get("treatment_periods", []),
    )
