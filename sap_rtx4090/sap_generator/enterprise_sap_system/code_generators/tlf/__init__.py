#!/usr/bin/env python3
"""
TLF (Tables, Listings, Figures) Code Generators
================================================

Generates production-ready SAS code for standard clinical trial outputs:

Tables:
- Demographics and baseline characteristics
- Adverse event summaries
- Primary efficacy analyses
- Secondary efficacy analyses

Listings:
- Patient demographics
- Adverse events (all, SAE, drug-related)

Figures:
- Forest plots for subgroup analyses
"""

from .t_demog import DemographicsTableGenerator
from .t_ae_summary import AESummaryTableGenerator
from .t_primary import PrimaryEfficacyTableGenerator
from .t_secondary import SecondaryEfficacyTableGenerator
from .l_demog import DemographicsListingGenerator
from .l_ae import AdverseEventsListingGenerator
from .f_forest import ForestPlotGenerator

__all__ = [
    # Tables
    'DemographicsTableGenerator',
    'AESummaryTableGenerator',
    'PrimaryEfficacyTableGenerator',
    'SecondaryEfficacyTableGenerator',
    # Listings
    'DemographicsListingGenerator',
    'AdverseEventsListingGenerator',
    # Figures
    'ForestPlotGenerator',
]
