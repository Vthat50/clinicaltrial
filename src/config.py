"""Configuration settings for the clinical trial pipeline."""
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROTOCOLS_DIR = RAW_DIR / "protocols"
SAPS_DIR = RAW_DIR / "saps"
PROCESSED_DIR = DATA_DIR / "processed"
DATABASE_DIR = DATA_DIR / "database"

# Database
DATABASE_PATH = DATABASE_DIR / "clinical_trials.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Trial metadata
TRIAL_METADATA = {
    "NCT01772472": {"condition": "Breast (HER2+)", "name": "KATHERINE", "drug": "T-DM1"},
    "NCT02855944": {"condition": "Ovarian (BRCA)", "name": "ARIEL4", "drug": "Rucaparib"},
    "NCT03337724": {"condition": "Breast (TNBC)", "name": "Ipatasertib", "drug": "Ipatasertib"},
    "NCT04005716": {"condition": "NSCLC", "name": "Tislelizumab", "drug": "Tislelizumab"},
    "NCT03777657": {"condition": "Esophageal", "name": "Tislelizumab", "drug": "Tislelizumab"},
    "NCT02402062": {"condition": "Neuroendocrine", "name": "SUNINET", "drug": "Sunitinib"},
    "NCT01515748": {"condition": "Gastric", "name": "DOS", "drug": "DOS chemotherapy"},
    "NCT04648033": {"condition": "NSCLC", "name": "ARCADIAN", "drug": "Various"},
    "NCT02705105": {"condition": "Solid Tumors", "name": "Precision Oncology", "drug": "Various"},
    "NCT05126433": {"condition": "Solid Tumors", "name": "Lurbinectedin", "drug": "Lurbinectedin"},
}

# Ensure directories exist
for dir_path in [PROTOCOLS_DIR, SAPS_DIR, PROCESSED_DIR, DATABASE_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)
