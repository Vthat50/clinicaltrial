"""Main TLF shell generation orchestrator.

Domain-by-domain loop: for each domain, load instructions, inject matched
reference examples + prior domain context, call Claude, collect results.
"""

import json
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Any, Optional

import anthropic

from .numbering import assign_numbers
from .prompts import METADATA_EXTRACTION_PROMPT, SYSTEM_PROMPT, USER_TEMPLATE
from .reference_library import (
    ReferenceLibrary,
    StudyProfile,
    build_study_profile,
    _parse_json_from_response,
)
from .renderer import render_docx, render_markdown
from .skills import DOMAIN_ORDER, SkillLoader

logger = logging.getLogger(__name__)

# Maximum protocol text length to include in each domain call
_MAX_PROTOCOL_CHARS = 100_000

# Claude model to use
_MODEL = os.environ.get("TLF_LLM_MODEL", "claude-sonnet-4-20250514")


# ---------------------------------------------------------------------------
# LLM caller
# ---------------------------------------------------------------------------

def _get_client() -> anthropic.AsyncAnthropic:
    """Get an Anthropic client (uses ANTHROPIC_API_KEY env var)."""
    return anthropic.AsyncAnthropic()


async def _call_claude(system_prompt: str, user_message: str, max_tokens: int = 64000) -> str:
    """Make a single Claude API call and return the text response.

    Uses streaming to avoid the 10-minute timeout on long requests.
    """
    client = _get_client()
    text_parts: list[str] = []
    async with client.messages.stream(
        model=_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        async for text in stream.text_stream:
            text_parts.append(text)
    return "".join(text_parts)


# ---------------------------------------------------------------------------
# Metadata extraction (lightweight — just for example matching)
# ---------------------------------------------------------------------------

async def _extract_metadata(protocol_text: str) -> dict:
    """Extract lightweight study metadata from protocol text via Claude.

    Used when no existing extraction dict is available (direct upload mode).
    """
    truncated = protocol_text[:_MAX_PROTOCOL_CHARS]
    prompt = METADATA_EXTRACTION_PROMPT.format(protocol_text=truncated)
    response = await _call_claude(
        "Extract clinical trial metadata. Return valid JSON only.",
        prompt,
        max_tokens=4096,
    )
    result = _parse_json_from_response(response)

    # Wrap in the schema shape that build_study_profile expects
    arm_names = result.get("arm_names", [])
    return {
        "study_design": {
            "phase": result.get("phase", ""),
            "type": result.get("design_type", ""),
            "has_central_review": result.get("has_central_review", False),
        },
        "arms": [{"name": name} for name in arm_names] if arm_names else [{}] * result.get("num_arms", 1),
        "assessments_collected": {
            "pk": result.get("has_pk", False),
            "immunogenicity": result.get("has_immunogenicity", False),
            "qol": result.get("has_qol", False),
        },
        "treatment_periods": result.get("treatment_periods", []),
        "therapeutic_area": result.get("therapeutic_area", ""),
        "populations": result.get("populations", []),
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_extraction_context(extraction: Optional[dict]) -> str:
    """Format the existing extraction dict as supplementary context."""
    if not extraction:
        return "No pre-extracted context available."

    parts = []

    # Study design
    sd = extraction.get("study_design", {})
    if sd:
        parts.append(f"**Study Design:** {sd.get('type', '?')}, {sd.get('phase', '?')}, "
                      f"blinding: {sd.get('blinding', '?')}")

    # Arms
    arms = extraction.get("arms", [])
    if arms:
        arm_strs = [a.get("name", "?") for a in arms if isinstance(a, dict)]
        parts.append(f"**Arms:** {', '.join(arm_strs)}")

    # Populations
    pops = extraction.get("populations", [])
    if pops:
        pop_strs = [f"{p.get('name', '?')} (primary for: {p.get('primary_for', '?')})"
                     for p in pops if isinstance(p, dict)]
        parts.append(f"**Populations:** {'; '.join(pop_strs)}")

    # Endpoints
    endpoints = extraction.get("endpoints", [])
    if endpoints:
        parts.append("**Endpoints:**")
        for ep in endpoints:
            if isinstance(ep, dict):
                primary = "PRIMARY" if ep.get("primary") else "secondary"
                parts.append(f"  - [{primary}] {ep.get('name', '?')} ({ep.get('type', '?')})")

    # Assessments
    assessments = extraction.get("assessments_collected", {})
    if assessments:
        flags = []
        for key, val in assessments.items():
            if isinstance(val, bool) and val:
                flags.append(key)
            elif isinstance(val, list) and val:
                flags.append(f"{key}: {', '.join(str(v) for v in val)}")
        if flags:
            parts.append(f"**Assessments collected:** {'; '.join(flags)}")

    # AESIs
    aesis = extraction.get("aesis", [])
    if aesis:
        aesi_names = [a.get("name", "?") for a in aesis if isinstance(a, dict)]
        parts.append(f"**AESIs:** {', '.join(aesi_names)}")

    # Lab panels
    labs = extraction.get("lab_panels", [])
    if labs:
        lab_names = [l.get("name", "?") for l in labs if isinstance(l, dict)]
        parts.append(f"**Lab panels:** {', '.join(lab_names)}")

    return "\n".join(parts) if parts else "No pre-extracted context available."


def _format_prior_tlfs(
    tables: list[dict], figures: list[dict], listings: list[dict]
) -> str:
    """Format previously generated TLFs as compact context."""
    if not tables and not figures and not listings:
        return "None yet (this is the first domain)."

    parts = []
    if tables:
        parts.append("**Tables already generated:**")
        for t in tables:
            parts.append(f"  - {t.get('title', '?')} [type={t.get('type', '?')}]")
    if figures:
        parts.append("**Figures already generated:**")
        for f in figures:
            parts.append(f"  - {f.get('title', '?')}")
    if listings:
        parts.append("**Listings already generated:**")
        for li in listings:
            parts.append(f"  - {li.get('title', '?')}")

    return "\n".join(parts)


def _format_prior_facts(domain_facts: dict[str, dict]) -> str:
    """Format extracted_facts from prior domains as context."""
    if not domain_facts:
        return "None yet (this is the first domain)."

    parts = []
    for domain, facts in domain_facts.items():
        if not facts or not isinstance(facts, dict):
            continue
        # Include key facts that downstream domains need
        important = {}
        for k, v in facts.items():
            k_lower = k.lower()
            if any(term in k_lower for term in (
                "endpoint", "population", "arm", "panel", "period",
                "design", "aesi", "instrument", "analyte",
            )):
                important[k] = v
        if important:
            parts.append(f"**{domain}**: {json.dumps(important, default=str)}")

    if not parts:
        return "None yet (this is the first domain)."
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate(items: list[dict]) -> list[dict]:
    """Remove exact-duplicate entries based on title + population.

    Uses exact matching only. Fuzzy matching was removing legitimate tables
    that differ by endpoint name or population name.
    """
    if not items:
        return items

    seen_keys: set[str] = set()
    unique = []
    for item in items:
        title = item.get("title", "").lower().strip()
        pop = item.get("population", "").lower().strip()
        key = f"{title}||{pop}"
        if key not in seen_keys:
            unique.append(item)
            seen_keys.add(key)
        else:
            logger.debug(f"Deduplicated: {item.get('title')}")

    return unique


# ---------------------------------------------------------------------------
# Population resolution (reuse from existing system if available)
# ---------------------------------------------------------------------------

def _try_resolve_populations(
    items: list[dict], extraction: Optional[dict]
) -> None:
    """Attempt to resolve generic population hints to protocol-specific names.

    Uses the population resolver from tlf_skills.py if available, otherwise
    does a simple lookup from the extraction's populations list.
    """
    if not extraction:
        return

    # Try importing the existing resolver
    try:
        from tlf_skills import _resolve_population
        facts = extraction
        for item in items:
            pop = item.get("population")
            if pop:
                item["population"] = _resolve_population(facts, pop)
        return
    except ImportError:
        pass

    # Fallback: simple lookup from extraction populations
    pops = extraction.get("populations", [])
    if not pops:
        return

    # Build a map: primary_for → population name
    pop_map = {}
    for p in pops:
        if isinstance(p, dict):
            primary_for = (p.get("primary_for") or "").lower()
            name = p.get("name", "")
            if primary_for and name:
                pop_map[primary_for] = name

    hint_to_domain = {
        "safety": "safety",
        "itt": "efficacy",
        "fas": "efficacy",
        "full analysis set": "efficacy",
        "pk": "pk",
        "pk evaluable": "pk",
        "ada evaluable": "immunogenicity",
    }

    for item in items:
        pop = item.get("population", "")
        domain = hint_to_domain.get(pop.lower())
        if domain and domain in pop_map:
            item["population"] = pop_map[domain]


# ---------------------------------------------------------------------------
# Gap validation and retry
# ---------------------------------------------------------------------------

_GAP_FILL_PROMPT = """You are a senior biostatistician. You previously generated TLF shells but missed some.

Generate ONLY the missing tables listed below. Use the same JSON format as before:
{{"tables": [...]}}

Each table must include complete columns, rows, footnotes, source, orientation.
Use the protocol text to fill in arm names, endpoint details, and population definitions.

## Protocol
{protocol_text}

## Supplementary Context
{extraction_context}

## Missing Tables to Generate
{missing_description}

Output valid JSON only.
"""


async def _fill_efficacy_gaps(
    domain_facts: dict,
    existing_tables: list[dict],
    protocol_excerpt: str,
    extraction_context: str,
) -> list[dict]:
    """Check extracted_facts for endpoint x population gaps and fill them."""
    gap_tables: list[dict] = []

    for domain in ("primary-efficacy", "secondary-efficacy"):
        facts = domain_facts.get(domain, {})
        if not facts:
            continue

        # Get endpoints and populations from extracted_facts
        # LLM uses varying key names — search all plausible variants
        endpoints = []
        for k, v in facts.items():
            k_lower = k.lower()
            if ("endpoint" in k_lower) and isinstance(v, (list, dict)):
                if isinstance(v, dict):
                    endpoints = list(v.keys())
                elif isinstance(v, list) and v:
                    # Could be list of strings or list of dicts
                    if isinstance(v[0], str):
                        endpoints = v
                    elif isinstance(v[0], dict):
                        # Try to extract endpoint names from dicts
                        for item in v:
                            name = item.get("name", item.get("endpoint", item.get("title", "")))
                            if name:
                                endpoints.append(str(name))
                if endpoints:
                    break
            elif ("endpoint" in k_lower) and isinstance(v, str) and v:
                endpoints = [v]
                break

        populations = []
        for k, v in facts.items():
            k_lower = k.lower()
            if ("population" in k_lower) and isinstance(v, (list, dict)):
                if isinstance(v, dict):
                    populations = list(v.keys())
                elif isinstance(v, list) and v:
                    if isinstance(v[0], str):
                        populations = v
                    elif isinstance(v[0], dict):
                        for item in v:
                            name = item.get("name", item.get("population", ""))
                            if name:
                                populations.append(str(name))
                if populations:
                    break

        print(f"[TLF LLM] {domain} extracted_facts: endpoints={endpoints}, populations={populations}")

        if not endpoints or not populations:
            print(f"[TLF LLM] {domain}: skipping gap fill — endpoints or populations empty")
            continue

        # Normalize to lists of strings
        if isinstance(endpoints, dict):
            endpoints = list(endpoints.keys())
        if isinstance(populations, dict):
            populations = list(populations.keys())
        endpoints = [str(e) if not isinstance(e, str) else e for e in endpoints]
        populations = [str(p) if not isinstance(p, str) else p for p in populations]

        if len(populations) < 2:
            continue  # No cross-product issue with single population

        # Count tables per population — if any population has fewer tables, retry
        pop_aliases = {}
        for pop in populations:
            aliases = [pop.lower()]
            p = pop.lower()
            if "intent" in p or "itt" in p:
                aliases.extend(["itt", "intent-to-treat", "intent to treat"])
            if "per-protocol" in p or "per protocol" in p or p == "pp":
                aliases.extend(["pp", "per-protocol", "per protocol"])
            pop_aliases[pop] = aliases

        # Count efficacy tables per population
        pop_counts = {}
        for pop in populations:
            count = 0
            for t in existing_tables:
                if not t.get("type", "").startswith("efficacy"):
                    continue
                title_and_pop = t.get("title", "").lower() + " " + t.get("population", "").lower()
                if any(re.search(r'\b' + re.escape(a) + r'\b', title_and_pop) for a in pop_aliases[pop]):
                    count += 1
            pop_counts[pop] = count

        print(f"[TLF LLM] {domain}: population table counts: {pop_counts}")

        max_count = max(pop_counts.values())
        underserved_pops = [p for p, c in pop_counts.items() if c < max_count]

        if not underserved_pops:
            print(f"[TLF LLM] {domain}: all populations have equal table counts ({max_count})")
            continue

        print(f"[TLF LLM] {domain}: underserved populations: {underserved_pops} — making retry call")

        missing_desc = (
            f"Domain: {domain}\n"
            f"Endpoints found in protocol: {', '.join(endpoints)}\n"
            f"ALL analysis populations: {', '.join(populations)}\n\n"
            f"Table counts per population: {pop_counts}\n"
            f"These populations have fewer tables: {', '.join(underserved_pops)}\n"
            f"Generate the missing tables so every population has a complete set.\n"
            f"Every endpoint below needs a table for each underserved population:\n"
            + "\n".join(f"- {ep}" for ep in endpoints)
        )

        try:
            response = await _call_claude(
                SYSTEM_PROMPT,
                _GAP_FILL_PROMPT.format(
                    protocol_text=protocol_excerpt[:50000],
                    extraction_context=extraction_context,
                    missing_description=missing_desc,
                ),
            )
            result = _parse_json_from_response(response)
            new_tables = result.get("tables", [])
            gap_tables.extend(new_tables)
            logger.info(f"[TLF LLM] Gap fill {domain}: {len(new_tables)} tables added")
        except Exception as e:
            logger.error(f"[TLF LLM] Gap fill {domain} failed: {e}")

    return gap_tables


async def _fill_lab_gaps(
    domain_facts: dict,
    existing_tables: list[dict],
    protocol_excerpt: str,
    extraction_context: str,
) -> list[dict]:
    """Check extracted_facts for lab panel gaps and fill them."""
    # Collect lab_panels from ALL domains that reported them, use the longest list
    all_panel_lists = []
    for domain_name, facts in domain_facts.items():
        if not facts or not isinstance(facts, dict):
            continue
        for k, v in facts.items():
            k_lower = k.lower()
            if ("panel" in k_lower) and isinstance(v, (list, dict)):
                found = []
                if isinstance(v, dict):
                    found = list(v.keys())
                elif isinstance(v, list) and v:
                    if isinstance(v[0], str):
                        found = v
                    elif isinstance(v[0], dict):
                        for item in v:
                            name = item.get("name", item.get("panel", ""))
                            if name:
                                found.append(str(name))
                if found:
                    print(f"[TLF LLM] lab_panels from {domain_name}: {found}")
                    all_panel_lists.append(found)

    # Use the longest list (most complete)
    panels = max(all_panel_lists, key=len) if all_panel_lists else []
    print(f"[TLF LLM] safety-labs best lab_panels list ({len(panels)} panels): {panels}")

    if not panels:
        print("[TLF LLM] safety-labs: no lab_panels found in extracted_facts — skipping gap fill")
        return []

    if isinstance(panels, dict):
        panels = list(panels.keys())
    panels = [str(p) if not isinstance(p, str) else p for p in panels]

    # Count-based check: N panels → at least 2×N lab tables (summary + shift each)
    lab_tables = [
        t for t in existing_tables
        if t.get("type", "") in ("labs_summary", "labs_shift")
    ]
    expected = len(panels) * 2
    actual = len(lab_tables)

    print(f"[TLF LLM] safety-labs: {len(panels)} panels × 2 = {expected} expected, {actual} actual lab tables")

    missing = []
    if actual < expected:
        missing.append(f"Generated {actual} lab tables but need at least {expected}")

    print(f"[TLF LLM] safety-labs: {len(missing)} missing lab tables: {missing}")

    if not missing:
        print("[TLF LLM] safety-labs: all panels have summary + shift tables")
        return []

    print(
        f"[TLF LLM] safety-labs: making retry call for {len(missing)} missing tables"
    )

    missing_desc = (
        f"Domain: safety-labs\n"
        f"Lab panels found in protocol: {', '.join(panels)}\n\n"
        f"You generated {actual} lab tables but need at least {expected} "
        f"(one summary + one shift per panel).\n"
        f"Generate ONLY the missing tables. Each panel below needs both a "
        f"Summary by Visit table AND a Shift table:\n"
        + "\n".join(f"- {p}" for p in panels)
    )

    try:
        response = await _call_claude(
            SYSTEM_PROMPT,
            _GAP_FILL_PROMPT.format(
                protocol_text=protocol_excerpt[:50000],
                extraction_context=extraction_context,
                missing_description=missing_desc,
            ),
        )
        result = _parse_json_from_response(response)
        new_tables = result.get("tables", [])
        logger.info(f"[TLF LLM] Gap fill safety-labs: {len(new_tables)} tables added")
        return new_tables
    except Exception as e:
        logger.error(f"[TLF LLM] Gap fill safety-labs failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def generate_tlf_shells_llm(
    protocol_text: str,
    extraction: Optional[dict] = None,
    output_format: str = "markdown",
) -> Any:
    """Generate TLF shells using LLM-driven domain-by-domain approach.

    Args:
        protocol_text: Full protocol text.
        extraction: Optional pre-extracted facts dict (from SAP job).
        output_format: "markdown", "docx", or "json".

    Returns:
        Markdown string, DOCX bytes, or dict depending on output_format.
    """
    logger.info("[TLF LLM] Starting LLM-driven TLF shell generation")

    # Truncate protocol for prompt context
    protocol_excerpt = protocol_text[:_MAX_PROTOCOL_CHARS]

    # Step 1: Build study profile for example matching
    if extraction and extraction.get("study_design"):
        logger.info("[TLF LLM] Using existing extraction for study profile")
        profile = build_study_profile(extraction)
    else:
        logger.info("[TLF LLM] Extracting metadata from protocol text")
        metadata = await _extract_metadata(protocol_text)
        profile = build_study_profile(metadata)
        # Use the metadata as supplementary context if no extraction provided
        if not extraction:
            extraction = metadata

    logger.info(
        f"[TLF LLM] Study profile: {profile.therapeutic_area}, "
        f"{profile.phase}, {profile.design_type}, {profile.num_arms} arms"
    )

    # Step 2: Find similar reference SAPs (LLM-based matching)
    library = ReferenceLibrary.get_instance()
    library.load()
    matches = await library.find_similar(
        profile, top_k=3, llm_caller=_call_claude
    )
    logger.info(f"[TLF LLM] Matched {len(matches)} reference studies")

    # Step 3: Domain-by-domain generation
    skill_loader = SkillLoader.get_instance()
    all_tables: list[dict] = []
    all_figures: list[dict] = []
    all_listings: list[dict] = []
    domain_facts: dict[str, dict] = {}

    extraction_context = _format_extraction_context(extraction)

    # Efficacy domains that need per-population splitting
    _EFFICACY_DOMAINS = {"primary-efficacy", "secondary-efficacy"}

    for domain in DOMAIN_ORDER:
        if not skill_loader.should_run(domain, profile):
            logger.info(f"[TLF LLM] Skipping domain: {domain} (condition not met)")
            continue

        logger.info(f"[TLF LLM] Generating domain: {domain}")

        skill_content = skill_loader.load_skill(domain)
        domain_examples = library.format_domain_examples(matches, domain)

        # For efficacy domains, check for multiple populations
        populations_to_split = []
        if domain in _EFFICACY_DOMAINS:
            # First check extraction metadata (most reliable source)
            ext_pops = extraction.get("populations", []) if extraction else []
            if isinstance(ext_pops, list) and len(ext_pops) >= 2:
                for p in ext_pops:
                    if isinstance(p, dict):
                        name = p.get("name", p.get("population", ""))
                        if name:
                            populations_to_split.append(str(name))
                    elif isinstance(p, str) and p:
                        populations_to_split.append(p)


        if domain in _EFFICACY_DOMAINS:
            print(f"[TLF LLM] {domain}: populations_to_split = {populations_to_split}")

        if domain in _EFFICACY_DOMAINS and len(populations_to_split) >= 2:
            # Make one call per population
            print(f"[TLF LLM] {domain}: splitting into {len(populations_to_split)} calls by population: {populations_to_split}")
            combined_facts = {}
            # Snapshot tables BEFORE this domain's splits so each population call
            # only sees tables from OTHER domains, not from sibling population calls
            tables_before_split = list(all_tables)
            figures_before_split = list(all_figures)
            listings_before_split = list(all_listings)
            for pop_idx, pop_name in enumerate(populations_to_split):
                prior_tlfs = _format_prior_tlfs(tables_before_split, figures_before_split, listings_before_split)
                prior_facts = _format_prior_facts(domain_facts)

                pop_instruction = (
                    f"\n\n## POPULATION FOCUS\n\n"
                    f"Generate tables ONLY for the **{pop_name}** population. "
                    f"Every table title must include \"{pop_name}\". "
                    f"Generate a complete set of tables for ALL endpoints using this population only."
                )

                user_message = USER_TEMPLATE.format(
                    protocol_text=protocol_excerpt,
                    extraction_context=extraction_context,
                    skill_content=skill_content + pop_instruction,
                    domain_examples=domain_examples,
                    prior_tlfs=prior_tlfs,
                    prior_facts=prior_facts,
                    domain_name=domain,
                )

                print(f"[TLF LLM] {domain} [{pop_name}]: prompt size = {len(user_message)} chars, ~{len(user_message)//4} tokens")

                try:
                    response = await _call_claude(SYSTEM_PROMPT, user_message)
                    print(f"[TLF LLM] {domain} [{pop_name}]: response size = {len(response)} chars, ~{len(response)//4} tokens")
                    result = _parse_json_from_response(response)

                    # Merge extracted_facts from each call
                    pop_facts = result.get("extracted_facts", {})
                    if pop_idx == 0:
                        combined_facts = pop_facts
                    else:
                        combined_facts.update(pop_facts)

                    new_tables = result.get("tables", [])
                    new_figures = result.get("figures", [])
                    new_listings = result.get("listings", [])

                    all_tables.extend(new_tables)
                    all_figures.extend(new_figures)
                    all_listings.extend(new_listings)

                    print(
                        f"[TLF LLM] Domain {domain} [{pop_name}]: "
                        f"{len(new_tables)} tables, {len(new_figures)} figures, "
                        f"{len(new_listings)} listings"
                    )

                except Exception as e:
                    logger.error(f"[TLF LLM] Domain {domain} [{pop_name}] failed: {e}")
                    continue

            domain_facts[domain] = combined_facts

        else:
            # Standard single call for non-efficacy domains or single-population
            prior_tlfs = _format_prior_tlfs(all_tables, all_figures, all_listings)
            prior_facts = _format_prior_facts(domain_facts)

            user_message = USER_TEMPLATE.format(
                protocol_text=protocol_excerpt,
                extraction_context=extraction_context,
                skill_content=skill_content,
                domain_examples=domain_examples,
                prior_tlfs=prior_tlfs,
                prior_facts=prior_facts,
                domain_name=domain,
            )

            print(f"[TLF LLM] {domain}: prompt size = {len(user_message)} chars, ~{len(user_message)//4} tokens")

            try:
                response = await _call_claude(SYSTEM_PROMPT, user_message)
                print(f"[TLF LLM] {domain}: response size = {len(response)} chars, ~{len(response)//4} tokens")
                result = _parse_json_from_response(response)

                domain_facts[domain] = result.get("extracted_facts", {})

                new_tables = result.get("tables", [])
                new_figures = result.get("figures", [])
                new_listings = result.get("listings", [])

                all_tables.extend(new_tables)
                all_figures.extend(new_figures)
                all_listings.extend(new_listings)

                print(
                    f"[TLF LLM] Domain {domain}: "
                    f"{len(new_tables)} tables, {len(new_figures)} figures, "
                    f"{len(new_listings)} listings"
                )

            except Exception as e:
                logger.error(f"[TLF LLM] Domain {domain} failed: {e}")
                continue

            # Fallback: if this was an efficacy domain that ran without splitting,
            # check its extracted_facts for multiple populations and re-run for missing ones
            if domain in _EFFICACY_DOMAINS:
                facts = domain_facts.get(domain, {})
                found_pops = []
                for k, v in facts.items():
                    if "population" in k.lower() and isinstance(v, list):
                        for item in v:
                            if isinstance(item, str) and item:
                                found_pops.append(item)
                            elif isinstance(item, dict):
                                name = item.get("name", item.get("population", ""))
                                if name:
                                    found_pops.append(str(name))
                        break

                if len(found_pops) >= 2:
                    # Check which populations are already covered in existing tables
                    existing_pops = set()
                    for t in new_tables:
                        title_lower = t.get("title", "").lower()
                        pop_lower = t.get("population", "").lower()
                        for fp in found_pops:
                            if fp.lower() in title_lower or fp.lower() in pop_lower:
                                existing_pops.add(fp)

                    missing_pops = [p for p in found_pops if p not in existing_pops]
                    if missing_pops:
                        print(f"[TLF LLM] {domain} FALLBACK: found populations {found_pops}, missing {missing_pops}. Re-running for missing.")
                        for pop_name in missing_pops:
                            prior_tlfs = _format_prior_tlfs(all_tables, all_figures, all_listings)
                            prior_facts = _format_prior_facts(domain_facts)
                            pop_instruction = (
                                f"\n\n## POPULATION FOCUS\n\n"
                                f"Generate tables ONLY for the **{pop_name}** population. "
                                f"Every table title must include \"{pop_name}\". "
                                f"Generate a complete set of tables for ALL endpoints using this population only."
                            )
                            user_message = USER_TEMPLATE.format(
                                protocol_text=protocol_excerpt,
                                extraction_context=extraction_context,
                                skill_content=skill_content + pop_instruction,
                                domain_examples=domain_examples,
                                prior_tlfs=prior_tlfs,
                                prior_facts=prior_facts,
                                domain_name=domain,
                            )
                            try:
                                print(f"[TLF LLM] {domain} FALLBACK [{pop_name}]: calling Claude")
                                resp = await _call_claude(SYSTEM_PROMPT, user_message)
                                fb_result = _parse_json_from_response(resp)
                                fb_tables = fb_result.get("tables", [])
                                fb_figures = fb_result.get("figures", [])
                                fb_listings = fb_result.get("listings", [])
                                all_tables.extend(fb_tables)
                                all_figures.extend(fb_figures)
                                all_listings.extend(fb_listings)
                                print(f"[TLF LLM] {domain} FALLBACK [{pop_name}]: {len(fb_tables)} tables, {len(fb_figures)} figures")
                            except Exception as e:
                                logger.error(f"[TLF LLM] {domain} FALLBACK [{pop_name}] failed: {e}")
                    else:
                        print(f"[TLF LLM] {domain}: all populations covered: {existing_pops}")

    # Step 4: Log extracted facts (gap-fill disabled)
    print(f"[TLF LLM] domain_facts keys: {list(domain_facts.keys())}")
    for dk, dv in domain_facts.items():
        if isinstance(dv, dict):
            print(f"[TLF LLM]   {dk} extracted_facts keys: {list(dv.keys())}")

    # Step 5: Post-process
    logger.info("[TLF LLM] Post-processing: dedup, number, resolve populations")

    # Dedup disabled — was removing legitimate cross-product tables
    # all_tables = _deduplicate(all_tables)
    # all_figures = _deduplicate(all_figures)
    # all_listings = _deduplicate(all_listings)

    assign_numbers(all_tables, all_figures, all_listings)

    # Population resolver disabled — was overwriting distinct populations with a single name
    # _try_resolve_populations(
    #     all_tables + all_figures + all_listings, extraction
    # )

    total = len(all_tables) + len(all_figures) + len(all_listings)
    logger.info(
        f"[TLF LLM] Complete: {len(all_tables)} tables, "
        f"{len(all_figures)} figures, {len(all_listings)} listings "
        f"({total} total)"
    )

    # Step 6: Format output
    if output_format == "json":
        return {
            "tables": all_tables,
            "figures": all_figures,
            "listings": all_listings,
            "domain_facts": domain_facts,
            "matched_references": [
                m.study.profile.nct_id for m in matches
            ],
            "study_profile": {
                "therapeutic_area": profile.therapeutic_area,
                "phase": profile.phase,
                "design_type": profile.design_type,
                "num_arms": profile.num_arms,
            },
        }
    elif output_format == "docx":
        return render_docx(all_tables, all_figures, all_listings)
    else:
        return render_markdown(
            all_tables, all_figures, all_listings, domain_facts
        )
