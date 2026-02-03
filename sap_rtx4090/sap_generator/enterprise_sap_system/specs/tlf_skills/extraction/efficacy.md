# Extraction: Efficacy Endpoints (ICH 14.2)

Each efficacy endpoint produces at least one analysis table. The number and type of tables depends on the endpoint type, the populations it's analyzed in, and any sensitivity or subgroup analyses the protocol defines.

## Where to Look

The objectives and endpoints section defines every endpoint. The statistical methods section describes how each endpoint is analyzed, including the analysis method, populations, sensitivity analyses, and multiplicity adjustments. The estimands section (if present) defines intercurrent event handling. The sample size section often reveals the primary analysis method.

## What to Think About

**What are all the endpoints?** Read the objectives section and extract every endpoint the protocol defines — primary, key secondary, secondary, and exploratory. For each endpoint, capture:
- The exact name as the protocol states it
- Whether it is primary, key secondary, secondary, or exploratory
- The type of measurement: is it a time-to-event outcome, a binary response, a continuous measure, a count/rate, or an ordinal score? The endpoint type determines which table template the generation layer uses.
- Which population it is analyzed in. The protocol specifies this — it may differ between primary and secondary endpoints.

**Does any endpoint have multiple analysis populations?** The primary endpoint is often analyzed in both the primary population and a sensitivity population. If the protocol says "the primary endpoint will also be analyzed in the per-protocol population," that's a second table for the same endpoint.

**Does any endpoint have multiple review types?** Some studies have both central review and local investigator review for the same endpoint. Each review type produces a separate table.

**What sensitivity analyses are defined?** Look for language like "sensitivity analysis," "supportive analysis," or "robustness analysis." Each distinct sensitivity analysis of the primary endpoint produces its own table. Sensitivity analyses may use a different population, a different statistical method, or a different handling of missing data.

**What subgroup analyses are pre-specified?** Look for a subgroup analysis section. Capture which endpoints have subgroup analyses and what subgroup variables are defined. Each endpoint with subgroups needs a subgroup analysis table and potentially a forest plot figure.

**What statistical methods does the protocol specify?** For each endpoint, does the protocol name a specific analysis method? If stated, capture it. If not, the generation layer will apply a default based on endpoint type.

**Are there multiplicity adjustments?** Does the protocol describe a testing hierarchy, gatekeeping procedure, or alpha-spending function? If so, note which endpoints are in the hierarchy and the testing order. This affects footnotes and whether p-values are labeled as "nominal."

**Are there responder analyses?** Does the protocol define response categories or responder thresholds for any endpoint? If so, these produce separate responder analysis tables.

**Are there any QoL or patient-reported outcome endpoints?** If the protocol specifies QoL instruments, capture each instrument name. Each instrument produces its own set of tables (summary by visit, change from baseline, and possibly a responder analysis).
