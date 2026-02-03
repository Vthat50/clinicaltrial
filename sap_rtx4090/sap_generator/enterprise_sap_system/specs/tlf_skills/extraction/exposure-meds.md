# Extraction: Exposure & Medications (ICH 14.3)

Exposure and concomitant medication tables are always included. But the specific tables depend on the dosing regimen, whether dose modifications are allowed, whether there is a backbone/background therapy, and whether rescue medications are defined.

## Where to Look

The study treatment section describes the dosing regimen, dose modification rules, and any background therapy. The prohibited/permitted medications section defines medication restrictions. The rescue therapy section (if present) describes what rescue is allowed and when. The SOA may show drug administration and compliance assessments.

## What to Think About

### Study Drug Exposure

**What is the dosing regimen?** Is it fixed-dose, weight-based, titrated, or cycle-based? This determines how exposure is summarized (duration in weeks vs. number of cycles vs. cumulative dose).

**Are dose modifications allowed?** If the protocol defines rules for dose reduction, dose interruption, dose delay, or dose escalation, then dose modification tables are needed. Capture that dose modifications exist and what types are allowed — the generation layer will build the appropriate tables.

**Is there a planned dose for calculating relative dose intensity?** If the protocol specifies a planned dose or planned number of cycles, relative dose intensity can be calculated.

### Backbone / Background Therapy

**Does the protocol require a background therapy that all subjects receive alongside the study drug?** This is different from concomitant medications — it's a required protocol-mandated therapy. If the protocol specifies a required background therapy, capture the drug name and that it exists. If there is no required background therapy, do NOT create backbone therapy tables.

**If there is a backbone, are dose modifications allowed for it?** If the protocol defines dose modification rules specifically for the backbone therapy, note it.

### Concomitant Medications

**Does the protocol distinguish prior from concomitant medications?** If the protocol defines these differently, both may need separate tables.

**Does the protocol define rescue or salvage therapy?** If the protocol specifies specific rescue medications, conditions that trigger rescue use, or escape criteria, note that rescue medication tables are needed.

**Are there prohibited medications?** If the protocol lists specific prohibited medications, this may warrant a "prohibited medication use" table to track protocol deviations.

### Special Considerations

**Is there a run-in or washout period?** If the protocol requires subjects to wash out from prior therapies before randomization, note it — this may affect the prior medication table structure.

**Are there multiple study drugs administered?** Some studies have combination therapy where subjects receive two or more study drugs. Each drug may need its own exposure table.
