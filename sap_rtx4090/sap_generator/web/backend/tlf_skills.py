"""
TLF Skills Module — Generic YAML Engine
=========================================
Reads SKILL.yaml files from tlf_skills/ and builds TLF shells deterministically.
No hardcoded builder functions — all logic is driven by YAML structure.

Architecture:
  SKILL.md (plain English, biostatistician edits)
    → convert_skills_to_yaml.py
    → SKILL.yaml (structured rules)
    → THIS MODULE reads SKILL.yaml at runtime

YAML section types handled:
  - tables:                 condition + items (disposition, safety-ae, labs, vitals, etc.)
  - endpoint_tables:        filter + type_mapping (primary-efficacy, secondary-efficacy)
  - subgroup_tables:        for_each endpoints with condition
  - aesi_tables:            for_each AESIs
  - period_split_tables:    for_each treatment periods
  - backbone_therapy_tables + backbone_therapy_listings: for_each backbone therapies
  - figure_rules:           for_each endpoints/instruments with conditions
  - listings:               condition + items (mandatory + conditional)

Usage:
  from tlf_skills import build_all_skills, get_available_skills, TLF_SKILL_ORDER

  result = build_all_skills(facts, selected_skills=["primary-efficacy", "labs"])
  result = build_all_skills(facts)  # all skills
  preview = get_available_skills(facts)
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any

from tlf_integration import (
    _load_yaml_configs,
    _evaluate_condition,
    _substitute_placeholders,
    _resolve_path,
    _build_endpoint_footnotes,
    _default_analysis_method,
    _TA_AREA_RULES,
)


# =============================================================================
# POPULATION RESOLVER
# =============================================================================

# Maps generic population hints from SKILL.yaml → primary_for domain values
_POP_DOMAIN_MAP = {
    "safety": "safety",
    "itt": "efficacy",
    "fas": "efficacy",
    "full analysis set": "efficacy",
    "intent-to-treat": "efficacy",
    "per-protocol": "efficacy",
    "pp": "efficacy",
    "pk": "pk",
    "pk evaluable": "pk",
    "pk population": "pk",
    "ada evaluable": "immunogenicity",
    "ada": "immunogenicity",
    "immunogenicity": "immunogenicity",
}

# Populations that refer to enrollment stage, not analysis — skip resolution
_ENROLLMENT_POPULATIONS = {"enrolled", "screened", "randomized"}


def _resolve_population(facts: Dict, population_hint: str) -> str:
    """Resolve a generic population label to the protocol-defined population name.

    Uses facts.populations[].primary_for to find the protocol's actual name.
    Falls back to the hint unchanged if no match is found.

    Examples:
      "Safety" + protocol defines "Safety Population" (primary_for: safety) → "Safety Population"
      "ITT"    + protocol defines "Full Analysis Set" (primary_for: efficacy) → "Full Analysis Set"
      "PK"     + protocol defines "PK Evaluable Population" (primary_for: pk) → "PK Evaluable Population"
    """
    if not population_hint:
        return population_hint

    hint_lower = population_hint.lower().strip()

    # Don't resolve enrollment-stage labels — these are universal
    if hint_lower in _ENROLLMENT_POPULATIONS:
        return population_hint

    populations = facts.get("populations", [])
    if not populations:
        return population_hint

    # 1. Exact name match — protocol already uses this name
    for pop in populations:
        if isinstance(pop, dict) and pop.get("name", "").lower().strip() == hint_lower:
            return pop["name"]

    # 2. Map hint to domain via _POP_DOMAIN_MAP, then match by primary_for
    domain = _POP_DOMAIN_MAP.get(hint_lower)
    if domain:
        for pop in populations:
            if isinstance(pop, dict) and pop.get("primary_for", "").lower() == domain:
                return pop.get("name", population_hint)

    # 3. Check pk_sampling.pk_population for PK-related hints
    if hint_lower in ("pk", "pk evaluable", "pk population"):
        pk_pop = facts.get("pk_sampling", {}).get("pk_population")
        if pk_pop:
            return pk_pop

    # 4. Substring match — hint appears in population name or vice versa
    for pop in populations:
        if isinstance(pop, dict):
            pop_name = pop.get("name", "").lower()
            if hint_lower in pop_name or pop_name in hint_lower:
                return pop["name"]

    # No match — return hint unchanged (the protocol may not define this population)
    return population_hint


def _resolve_all_populations(items: List[Dict], facts: Dict) -> None:
    """Resolve population hints in a list of table/listing/figure dicts in-place."""
    for item in items:
        pop = item.get("population")
        if pop:
            item["population"] = _resolve_population(facts, pop)


# =============================================================================
# SKILL YAML DISCOVERY
# =============================================================================

# Skills directory: enterprise_sap_system/specs/tlf_skills/
SKILLS_DIR = Path(__file__).parent.parent.parent / "enterprise_sap_system" / "specs" / "tlf_skills"

# Cache for loaded skill YAMLs
_SKILL_YAMLS: Optional[Dict[str, Dict]] = None


def _load_skill_yamls() -> Dict[str, Dict]:
    """Scan tlf_skills/ for SKILL.yaml files, load and cache them."""
    global _SKILL_YAMLS
    if _SKILL_YAMLS is not None:
        return _SKILL_YAMLS

    _SKILL_YAMLS = {}
    if not SKILLS_DIR.exists():
        print(f"[TLF Skills] WARNING: Skills directory not found: {SKILLS_DIR}")
        return _SKILL_YAMLS

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        yaml_path = skill_dir / "SKILL.yaml"
        if not yaml_path.exists():
            continue
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
            if data:
                skill_id = skill_dir.name
                _SKILL_YAMLS[skill_id] = data
        except Exception as e:
            print(f"[TLF Skills] WARNING: Failed to load {yaml_path}: {e}")

    print(f"[TLF Skills] Loaded {len(_SKILL_YAMLS)} skill YAMLs: {list(_SKILL_YAMLS.keys())}")
    return _SKILL_YAMLS


def _get_skill_order() -> List[str]:
    """Return skill IDs ordered by display_order from their YAML metadata."""
    yamls = _load_skill_yamls()
    skills = [(sid, data.get("display_order", 99)) for sid, data in yamls.items()]
    skills.sort(key=lambda x: x[1])
    return [s[0] for s in skills]


# =============================================================================
# GENERIC SKILL BUILDER
# =============================================================================

def _build_skill_from_yaml(skill_id: str, skill_yaml: Dict, facts: Dict) -> Dict:
    """
    Build tables/figures/listings from a single SKILL.yaml.
    Dispatches to the appropriate handler based on which keys are present.
    """
    ctx = {"facts": facts}
    tables = []
    figures = []
    listings = []

    # --- tables: condition + items ---
    if "tables" in skill_yaml:
        tables.extend(_process_table_groups(skill_yaml["tables"], facts, ctx))

    # --- endpoint_tables: filter + type_mapping + endpoint iteration ---
    if "endpoint_tables" in skill_yaml:
        tables.extend(_process_endpoint_tables(skill_yaml["endpoint_tables"], facts, ctx))

    # --- subgroup_tables: for_each endpoints with condition ---
    if "subgroup_tables" in skill_yaml:
        tables.extend(_process_subgroup_tables(skill_yaml["subgroup_tables"], facts, ctx))

    # --- aesi_tables: for_each AESIs ---
    if "aesi_tables" in skill_yaml:
        tables.extend(_process_aesi_tables(skill_yaml["aesi_tables"], facts, ctx))

    # --- period_split_tables: for_each treatment periods ---
    if "period_split_tables" in skill_yaml:
        tables.extend(_process_period_split_tables(skill_yaml["period_split_tables"], facts, ctx))

    # --- backbone_therapy_tables: for_each backbone therapies ---
    if "backbone_therapy_tables" in skill_yaml:
        tables.extend(_process_backbone_tables(skill_yaml["backbone_therapy_tables"], facts, ctx))

    # --- backbone_therapy_listings ---
    if "backbone_therapy_listings" in skill_yaml:
        listings.extend(_process_backbone_listings(skill_yaml["backbone_therapy_listings"], facts, ctx))

    # --- figure_rules ---
    if "figure_rules" in skill_yaml:
        figures.extend(_process_figure_rules(skill_yaml["figure_rules"], facts, ctx))

    # --- listings: condition + items ---
    if "listings" in skill_yaml:
        listings.extend(_process_listing_groups(skill_yaml["listings"], facts, ctx))

    # Resolve all generic population hints to protocol-defined names
    _resolve_all_populations(tables, facts)
    _resolve_all_populations(figures, facts)
    _resolve_all_populations(listings, facts)

    return {"tables": tables, "figures": figures, "listings": listings}


# =============================================================================
# SECTION TYPE HANDLERS
# =============================================================================

def _process_table_groups(groups: List[Dict], facts: Dict, ctx: Dict) -> List[Dict]:
    """
    Process 'tables' section — a list of groups, each with optional condition and items list.

    YAML structure:
      tables:
      - items:
        - {type, title, population}
        condition: "facts.assessments_collected.labs == true"  # optional
      - items:
        - {type, title, population}
    """
    tables = []
    for group in groups:
        cond = group.get("condition", "")
        if cond and not _evaluate_condition(cond, ctx):
            continue

        for_each = group.get("for_each")
        if for_each:
            items = _resolve_path(ctx, for_each) or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                # Resolve instrument name: use .name for dicts, raw value for strings
                if isinstance(item, dict):
                    inst_name = item.get("name", str(item))
                    item_ctx = {"instrument": inst_name, **item, "facts": facts}
                else:
                    item_ctx = {"instrument": item, "facts": facts}
                for tbl in group.get("items", []):
                    title = _substitute_placeholders(tbl.get("title", ""), item_ctx)
                    tables.append({
                        "type": tbl.get("type", ""),
                        "title": title,
                        "population": tbl.get("population", "Safety"),
                    })
        else:
            for tbl in group.get("items", []):
                entry = {
                    "type": tbl.get("type", ""),
                    "title": tbl.get("title", ""),
                    "population": tbl.get("population", "Safety"),
                }
                # Carry through optional columns if present
                if "columns" in tbl:
                    entry["columns"] = tbl["columns"]
                tables.append(entry)

    return tables


def _process_endpoint_tables(config: Dict, facts: Dict, ctx: Dict) -> List[Dict]:
    """
    Process 'endpoint_tables' section — iterates over facts.endpoints,
    filtered by config['filter'], maps endpoint type to table type.

    YAML structure:
      endpoint_tables:
        filter: "endpoint.primary == true"
        type_mapping: {time_to_event: time_to_event, binary: binary_response, ...}
        title_pattern: "{endpoint.name} ({population} Population)"
        title_with_review_pattern: "{endpoint.name} ({review} Review) ({population} Population)"
        generate_footnotes: true
    """
    tables = []
    endpoints = facts.get("endpoints", [])
    ep_filter = config.get("filter", "")
    type_mapping = config.get("type_mapping", {})
    title_pattern = config.get("title_pattern", "{endpoint.name} ({population} Population)")
    title_review_pattern = config.get("title_with_review_pattern",
                                       "{endpoint.name} ({review} Review) ({population} Population)")
    generate_footnotes = config.get("generate_footnotes", False)

    for ep in endpoints:
        # Evaluate filter against endpoint
        if ep_filter:
            ep_ctx = {"endpoint": ep, "facts": facts}
            if not _evaluate_condition(ep_filter, ep_ctx):
                continue

        # Assign default analysis method if missing
        if not ep.get("analysis_method"):
            ep["analysis_method"] = _default_analysis_method(ep.get("type"), facts)

        mapped_type = type_mapping.get(ep.get("type", ""), "continuous_endpoint")

        # Resolve population defaults to protocol-defined names before title substitution
        raw_pops = ep.get("populations", ["ITT"]) or ["ITT"]
        resolved_pops = [_resolve_population(facts, p) for p in raw_pops]

        for pop in resolved_pops:
            reviews = ep.get("reviews") or [None]
            for review in reviews:
                ep_ctx = {
                    "endpoint": ep,
                    "population": pop,
                    "review": review.title() if review else None,
                }
                pattern = title_review_pattern if review else title_pattern
                title = _substitute_placeholders(pattern, ep_ctx)

                entry = {
                    "type": mapped_type,
                    "title": title,
                    "population": pop,
                    "endpoint": ep.get("name", ""),
                    "analysis_method": ep.get("analysis_method"),
                }
                if generate_footnotes:
                    entry["footnotes"] = _build_endpoint_footnotes(ep, facts)
                extra = ep.get("extra_rows", [])
                if extra:
                    entry["extra_rows"] = extra

                # Inject protocol-specific details so the rendering layer
                # can build data-driven rows instead of using static templates
                landmark = ep.get("landmark_timepoints")
                if landmark:
                    entry["landmark_timepoints"] = landmark
                censoring = ep.get("censoring_rules")
                if censoring:
                    entry["censoring_rules"] = censoring
                covariates = ep.get("covariates")
                if covariates:
                    entry["covariates"] = covariates
                resp_criteria = ep.get("response_criteria")
                if resp_criteria:
                    entry["response_criteria"] = resp_criteria

                tables.append(entry)

        # Sensitivity analyses — only for primary endpoints to avoid combinatorial explosion
        sensitivity_analyses = ep.get("sensitivity_analyses", [])
        if sensitivity_analyses and ep.get("primary"):
            primary_pop = resolved_pops[0]
            for sa in sensitivity_analyses:
                sa_title = f"{ep.get('name', '')} - Sensitivity Analysis: {sa} ({primary_pop} Population)"
                tables.append({
                    "type": mapped_type,
                    "title": sa_title,
                    "population": primary_pop,
                    "endpoint": ep.get("name", ""),
                    "analysis_method": ep.get("analysis_method"),
                })

    return tables


def _process_subgroup_tables(config: Dict, facts: Dict, ctx: Dict) -> List[Dict]:
    """
    Process 'subgroup_tables' section — for_each endpoint matching condition.

    YAML structure:
      subgroup_tables:
        for_each: facts.endpoints
        condition: "endpoint.primary == true or endpoint.key_secondary == true"
        global_condition: "facts.subgroups | length > 0"
        type: subgroup_forest
        title_pattern: "Subgroup Analysis of {endpoint.name}"
        population: ITT
    """
    tables = []
    global_cond = config.get("global_condition", "")
    if global_cond and not _evaluate_condition(global_cond, ctx):
        return tables

    for_each = config.get("for_each", "facts.endpoints")
    items = _resolve_path(ctx, for_each) or []

    for item in items:
        item_ctx = {"endpoint": item, "facts": facts}
        item_cond = config.get("condition", "")
        if item_cond and not _evaluate_condition(item_cond, item_ctx):
            continue
        title = _substitute_placeholders(
            config.get("title_pattern", "Subgroup Analysis of {endpoint.name}"), item_ctx
        )
        tables.append({
            "type": config.get("type", "subgroup_forest"),
            "title": title,
            "population": config.get("population", "ITT"),
            "endpoint": item.get("name", "") if isinstance(item, dict) else str(item),
        })

    return tables


def _process_aesi_tables(config: Dict, facts: Dict, ctx: Dict) -> List[Dict]:
    """
    Process 'aesi_tables' section — for_each AESI.

    YAML structure:
      aesi_tables:
        for_each: facts.aesis
        type: ae_special
        title_pattern: "AESI - {aesi.name}"
        population: Safety
        extra_rows_from: aesi.definition
    """
    tables = []
    for_each = config.get("for_each", "facts.aesis")
    items = _resolve_path(ctx, for_each) or []

    for aesi in items:
        aesi_ctx = {"aesi": aesi, "facts": facts}
        title = _substitute_placeholders(
            config.get("title_pattern", "AESI - {aesi.name}"), aesi_ctx
        )
        entry = {
            "type": config.get("type", "ae_special"),
            "title": title,
            "population": config.get("population", "Safety"),
        }
        extra_from = config.get("extra_rows_from")
        if extra_from:
            val = _resolve_path(aesi_ctx, extra_from)
            entry["extra_rows"] = [val] if isinstance(val, str) else (val or [])
        tables.append(entry)

    return tables


def _process_period_split_tables(config: Dict, facts: Dict, ctx: Dict) -> List[Dict]:
    """
    Process 'period_split_tables' section — for_each treatment period.

    YAML structure:
      period_split_tables:
        condition: "facts.treatment_periods | length > 1"
        for_each: facts.treatment_periods
        tables:
        - {type, title_pattern, population, condition?}
    """
    tables = []
    cond = config.get("condition", "")
    if cond and not _evaluate_condition(cond, ctx):
        return tables

    for_each = config.get("for_each", "facts.treatment_periods")
    periods = _resolve_path(ctx, for_each) or []

    for period in periods:
        period_ctx = {"period": period, "facts": facts}
        for tbl in config.get("tables", []):
            tbl_cond = tbl.get("condition", "")
            if tbl_cond and not _evaluate_condition(tbl_cond, ctx):
                continue
            title = _substitute_placeholders(
                tbl.get("title_pattern", tbl.get("title", "")), period_ctx
            )
            tables.append({
                "type": tbl.get("type", ""),
                "title": title,
                "population": tbl.get("population", "Safety"),
            })

    return tables


def _process_backbone_tables(config: Dict, facts: Dict, ctx: Dict) -> List[Dict]:
    """
    Process 'backbone_therapy_tables' section — for_each backbone therapy.

    YAML structure:
      backbone_therapy_tables:
        for_each: facts.backbone_therapies
        type: exposure
        title_pattern: "{therapy.drug_name} Exposure"
        population: Safety
    """
    tables = []
    for_each = config.get("for_each", "facts.backbone_therapies")
    therapies = _resolve_path(ctx, for_each) or []

    for therapy in therapies:
        if isinstance(therapy, dict):
            drug_name = therapy.get("name", "")
        elif isinstance(therapy, str):
            drug_name = therapy.split(" ")[0]
        else:
            drug_name = str(therapy)
        therapy_ctx = {"therapy": {"drug_name": drug_name, **( therapy if isinstance(therapy, dict) else {})}, "facts": facts}
        title = _substitute_placeholders(
            config.get("title_pattern", "{therapy.drug_name} Exposure"), therapy_ctx
        )
        tables.append({
            "type": config.get("type", "exposure"),
            "title": title,
            "population": config.get("population", "Safety"),
        })

    return tables


def _process_backbone_listings(config: Dict, facts: Dict, ctx: Dict) -> List[Dict]:
    """
    Process 'backbone_therapy_listings' section.

    YAML structure:
      backbone_therapy_listings:
        listings:
        - {title, population, columns?}
    """
    listings = []
    therapies = facts.get("backbone_therapies", [])

    for therapy in therapies:
        if isinstance(therapy, dict):
            drug_name = therapy.get("name", "")
        elif isinstance(therapy, str):
            drug_name = therapy.split(" ")[0]
        else:
            drug_name = str(therapy)
        therapy_ctx = {"therapy": {"drug_name": drug_name}, "facts": facts}
        for lst in config.get("listings", []):
            title = _substitute_placeholders(lst.get("title", ""), therapy_ctx)
            listings.append({
                "type": "listing",
                "title": title,
                "population": lst.get("population", "Safety"),
                "variables": lst.get("columns", []),
            })

    return listings


def _process_figure_rules(rules: List[Dict], facts: Dict, ctx: Dict) -> List[Dict]:
    """
    Process 'figure_rules' section — list of figure rule dicts.

    YAML structure:
      figure_rules:
      - type: other
        title_pattern: "Kaplan-Meier Plot of {endpoint name}"
        for_each: facts.endpoints
        endpoint_field: endpoint.name
        global_condition: "..."
    """
    figures = []
    seen = set()  # (type, endpoint) dedup key — prevents duplicates when both extraction and deterministic rules fire

    for fig_rule in rules:
        global_cond = fig_rule.get("global_condition", "")
        if global_cond and not _evaluate_condition(global_cond, ctx):
            continue

        for_each = fig_rule.get("for_each")
        if for_each:
            items = _resolve_path(ctx, for_each) or []
            for item in items:
                # Support both endpoint dicts and figure_requirement dicts
                if isinstance(item, dict) and "for_endpoint" in item:
                    # This is a figure_requirement item from extraction
                    item_ctx = {"figure": item, "facts": facts}
                else:
                    item_ctx = {"endpoint": item, "facts": facts, "instrument": item}
                item_cond = fig_rule.get("condition", "")
                if item_cond and not _evaluate_condition(item_cond, item_ctx):
                    continue
                title = _substitute_placeholders(fig_rule.get("title_pattern", ""), item_ctx)
                ep_field = fig_rule.get("endpoint_field", "endpoint.name")
                ep_val = _resolve_path(item_ctx, ep_field)
                if ep_val is None and isinstance(item, dict):
                    ep_val = item.get("for_endpoint", "")
                fig_type = fig_rule.get("type", "figure")
                # Strip placeholders from type (e.g. "{figure.type}" stays as-is for extraction rules)
                dedup_key = (fig_type, ep_val or title)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                figures.append({
                    "type": fig_type,
                    "title": title,
                    "endpoint": ep_val or "",
                })
        else:
            title = _substitute_placeholders(fig_rule.get("title_pattern", ""), ctx)
            fig_type = fig_rule.get("type", "figure")
            dedup_key = (fig_type, title)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            figures.append({
                "type": fig_type,
                "title": title,
            })

    return figures


def _process_listing_groups(groups: List[Dict], facts: Dict, ctx: Dict) -> List[Dict]:
    """
    Process 'listings' section — same structure as table groups (condition + items),
    with optional for_each support.

    YAML structure:
      listings:
      - items:
        - {title, population, columns?}
        condition: "..."
      - for_each: facts.listing_domains
        title_pattern: "Listing of {domain}"
        population: Safety
    """
    listings = []
    seen_titles = set()  # dedup — prevents duplicates when both extraction and deterministic rules fire

    for group in groups:
        cond = group.get("condition", "")
        if cond and not _evaluate_condition(cond, ctx):
            continue

        for_each = group.get("for_each")
        if for_each:
            # Iterate over a collection (e.g. facts.listing_domains)
            items = _resolve_path(ctx, for_each) or []
            if not isinstance(items, list):
                items = [items]
            title_pattern = group.get("title_pattern", "{domain}")
            pop = group.get("population", "Safety")
            for item in items:
                if isinstance(item, str):
                    item_ctx = {"domain": item, "facts": facts}
                elif isinstance(item, dict):
                    item_ctx = {**item, "domain": item.get("name", ""), "facts": facts}
                else:
                    item_ctx = {"domain": str(item), "facts": facts}
                title = _substitute_placeholders(title_pattern, item_ctx)
                title_lower = title.lower().strip()
                if title_lower in seen_titles:
                    continue
                seen_titles.add(title_lower)
                listings.append({
                    "type": "listing",
                    "title": title,
                    "population": pop,
                })
        else:
            for lst in group.get("items", []):
                title = lst.get("title", "")
                title_lower = title.lower().strip()
                if title_lower in seen_titles:
                    continue
                seen_titles.add(title_lower)
                listings.append({
                    "type": "listing",
                    "title": title,
                    "population": lst.get("population", "Safety"),
                    "variables": lst.get("columns", []),
                })

    return listings


# =============================================================================
# PUBLIC API
# =============================================================================

# Expose skill order for external use
TLF_SKILL_ORDER: List[str] = []  # populated on first call


def _ensure_loaded():
    """Ensure skills are loaded and order is set."""
    global TLF_SKILL_ORDER
    _load_yaml_configs()
    yamls = _load_skill_yamls()
    if not TLF_SKILL_ORDER:
        TLF_SKILL_ORDER = _get_skill_order()
    return yamls


# Metadata dict keyed by skill_id — built from YAML frontmatter
TLF_SKILL_METADATA: Dict[str, Dict] = {}


def _ensure_metadata():
    """Build metadata dict from loaded YAML frontmatter."""
    global TLF_SKILL_METADATA
    if TLF_SKILL_METADATA:
        return TLF_SKILL_METADATA
    yamls = _ensure_loaded()
    for sid, data in yamls.items():
        TLF_SKILL_METADATA[sid] = {
            "name": data.get("name", sid),
            "description": data.get("description", ""),
            "ich_section": data.get("ich_section", ""),
            "display_order": data.get("display_order", 99),
        }
    return TLF_SKILL_METADATA


def build_skill(skill_id: str, facts: Dict) -> Dict:
    """Build TLFs for a single skill. Returns {"tables": [...], "figures": [...], "listings": [...]}."""
    yamls = _ensure_loaded()
    skill_yaml = yamls.get(skill_id)
    if not skill_yaml:
        raise ValueError(f"Unknown skill: {skill_id}")
    return _build_skill_from_yaml(skill_id, skill_yaml, facts)


def build_all_skills(facts: Dict, selected_skills: Optional[List[str]] = None) -> Dict:
    """
    Build TLFs for all (or selected) skills.
    Returns: {"study_info": {...}, "tables": [...], "figures": [...], "listings": [...], "skill_results": {...}}
    """
    yamls = _ensure_loaded()
    _ensure_metadata()
    skills_to_build = selected_skills or TLF_SKILL_ORDER

    all_tables = []
    all_figures = []
    all_listings = []
    skill_results = {}

    for skill_id in TLF_SKILL_ORDER:
        if skill_id not in skills_to_build:
            continue
        skill_yaml = yamls.get(skill_id)
        if not skill_yaml:
            continue
        result = _build_skill_from_yaml(skill_id, skill_yaml, facts)
        skill_results[skill_id] = {
            "tables": result["tables"],
            "figures": result["figures"],
            "listings": result["listings"],
            "table_count": len(result["tables"]),
            "figure_count": len(result["figures"]),
            "listing_count": len(result["listings"]),
        }
        all_tables.extend(result["tables"])
        all_figures.extend(result["figures"])
        all_listings.extend(result["listings"])

    # Apply therapeutic area rules (supplements core rules)
    global _TA_AREA_RULES
    if _TA_AREA_RULES and not selected_skills:
        ctx = {"facts": facts}
        ta = facts.get("therapeutic_area", "").lower().replace(" ", "_")
        area_rules = _TA_AREA_RULES.get("areas", {}).get(ta, {})
        if area_rules:
            existing_types = {t.get("type") for t in all_tables}
            added = 0
            for rule in area_rules.get("mandatory_table_types", []):
                ttype = rule["type"]
                if ttype not in existing_types:
                    cond = rule.get("condition", "")
                    if cond and not _evaluate_condition(cond, ctx):
                        continue
                    all_tables.append({"type": ttype, "title": "", "population": "Safety", "_from_area_rules": True})
                    existing_types.add(ttype)
                    added += 1
            for rule in area_rules.get("common_table_types", []):
                ttype = rule["type"]
                if ttype not in existing_types:
                    cond = rule.get("condition", "")
                    if cond and not _evaluate_condition(cond, ctx):
                        continue
                    all_tables.append({"type": ttype, "title": "", "population": "Safety", "_from_area_rules": True})
                    existing_types.add(ttype)
                    added += 1
            if added:
                print(f"[TLF Skills] Added {added} tables from {ta} area rules")

    # Build study_info — includes rendering-relevant facts
    arms = facts.get("arms", [])
    populations = facts.get("populations", [])
    study_info = {
        "arm_names": [a["name"] for a in arms],
        "populations": [p["name"] for p in populations],
        "study_periods": facts.get("study_periods", []),
        "stratification_factors": facts.get("stratification_factors", []),
        "therapeutic_area": facts.get("therapeutic_area", ""),
        "design_type": facts.get("study_design", {}).get("type", ""),
        # Rendering layer needs these for study-specific rows
        "disease_specific_baseline": facts.get("disease_specific_baseline", []),
        "discontinuation_reasons": facts.get("discontinuation_reasons", []),
        "aesis": facts.get("aesis", []),
        "safety_concerns": facts.get("safety_concerns", []),
        "dose_modifications": facts.get("dose_modifications", {}),
        "population_definitions": facts.get("populations", []),
        "age_strata": facts.get("age_strata", []),
        "multicenter_design": facts.get("multicenter_design", {}),
    }

    print(f"[TLF Skills] Built TLF list: {len(all_tables)} tables, {len(all_figures)} figures, {len(all_listings)} listings ({len(skills_to_build)} skills)")

    return {
        "study_info": study_info,
        "tables": all_tables,
        "figures": all_figures,
        "listings": all_listings,
        "skill_results": skill_results,
    }


def get_available_skills(facts: Dict) -> List[Dict]:
    """
    Preview which skills apply and how many TLFs each would produce.
    Returns list of skill dicts with counts, for frontend display.
    """
    yamls = _ensure_loaded()
    _ensure_metadata()
    result = []

    for skill_id in TLF_SKILL_ORDER:
        meta = TLF_SKILL_METADATA.get(skill_id, {})
        skill_yaml = yamls.get(skill_id)
        if not skill_yaml:
            continue
        built = _build_skill_from_yaml(skill_id, skill_yaml, facts)
        tc = len(built["tables"])
        fc = len(built["figures"])
        lc = len(built["listings"])
        total = tc + fc + lc
        result.append({
            "id": skill_id,
            "name": meta.get("name", skill_id),
            "description": meta.get("description", ""),
            "ich_section": meta.get("ich_section", ""),
            "display_order": meta.get("display_order", 99),
            "table_count": tc,
            "figure_count": fc,
            "listing_count": lc,
            "total_count": total,
            "has_content": total > 0,
        })

    return result
