# CDISC Controlled Terminology Cache

This directory contains cached NCI EVS CDISC Controlled Terminology packages.

## Structure

```
terminology/
├── 2024-09-27/              # Version-specific CT packages
│   ├── sdtm_codelists.json  # SDTM terminology
│   └── adam_codelists.json  # ADaM terminology
├── cache/                   # Temporary cache files
└── README.md                # This file
```

## Usage

Terminology is automatically loaded from this cache by the CDISCTerminologyService.
If packages are not found locally, they can be downloaded from NCI EVS using the download script.

## Download CT Packages

```bash
python scripts/download_cdisc_ct.py
```

## CT Version

Current default: **2024-09-27**

## Sources

- NCI EVS CDISC Terminology: https://evs.nci.nih.gov/ftp1/CDISC/
- API: https://api-evsrest.nci.nih.gov/api/v1

## File Format

CT packages are stored as JSON with the following structure:

```json
{
  "metadata": {
    "package_name": "sdtm-terminology-2024-09-27",
    "version": "2024-09-27",
    "effective_date": "2024-09-27",
    "package_type": "SDTM",
    "cached_at": "2024-01-09T00:00:00"
  },
  "codelists": {
    "C66734": {
      "name": "Sex",
      "submission_value": "SEX",
      "extensible": "No",
      "definition": "...",
      "items": [...]
    }
  }
}
```
