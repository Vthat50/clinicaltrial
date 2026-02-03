# Extraction: Adverse Events (ICH 14.3)

The AE section always produces a core set of tables (overview, by SOC/PT, serious, leading to discontinuation, leading to death). But the protocol may define additional AE categories, special groupings, or study-specific safety concerns that need their own tables.

## Where to Look

The safety assessment section describes AE collection, coding, and grading. The AE reporting section may define special categories. Look also for "Adverse Events of Special Interest," "Events of Clinical Interest," or "Targeted Safety Events" — these are sometimes in a separate subsection or appendix. The dose modification section describes which AEs trigger dose changes.

## What to Think About

**How does the protocol grade AE severity?** Does it use a standard grading system, or a study-specific grading scale? The grading system determines row labels in the overview table and whether grade-specific tables are needed.

**How does the protocol assess causality/relatedness?** Is it a binary assessment (related/not related) or a multi-category scale? This determines whether "treatment-related" tables are included and how relatedness is defined in footnotes.

**Does the protocol define a frequency threshold for the "common TEAEs" table?** Some protocols specify that only TEAEs occurring above a certain percentage threshold should be shown in a summary table. Look for this in the statistical methods section. If stated, capture the threshold. If not stated, the generation layer will use a standard threshold.

**Does the protocol define Adverse Events of Special Interest (AESIs)?** This is critical. AESIs are protocol-defined categories of AEs that require separate analysis. Each AESI produces its own table. Look for:
- A dedicated AESI section that names specific categories
- References to Standardised MedDRA Queries (SMQs) or custom preferred term lists
- Any AE category the protocol singles out for special monitoring or reporting

Capture every AESI the protocol defines, by name, exactly as stated.

**Does the protocol define grouped AE terms?** Beyond AESIs, protocols sometimes define custom groupings of AE preferred terms that should be analyzed together. These are specific to the drug's safety profile. Capture each group name.

**Does the route of administration create special AE categories?** Injectable drugs may have injection site reaction assessments. IV drugs may have infusion-related reaction monitoring. If the protocol describes a specific assessment for administration-related reactions, this needs its own table.

**Are there dose modification rules triggered by specific AEs?** If the protocol defines rules for dose reduction, interruption, or discontinuation based on specific AE types or grades, this implies a "TEAEs leading to dose modification" table and potentially tables showing which specific AEs triggered modifications.

**Are there protocol-defined stopping rules or safety signals?** If the protocol describes specific safety thresholds that would trigger study-level actions (DSMB review, enrollment hold), note them. These may imply threshold-based summary tables.

**Does the drug class have known safety concerns?** The protocol's safety section often references the drug class's known risks. These known risks typically generate focused analysis tables. The protocol may not call them "AESIs" explicitly, but if it dedicates paragraphs to a specific safety topic, that topic likely needs its own table.
