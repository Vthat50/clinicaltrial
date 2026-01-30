#!/bin/bash
# Download Oncology Protocols with SEPARATE Protocol and SAP files
# These are ideal for training: Protocol (input) → SAP (output)

mkdir -p oncology_pairs
cd oncology_pairs

echo "=== Downloading Protocol-SAP Pairs (Separate Files) ==="
echo ""

# 1. NCT01772472 - Breast Cancer KATHERINE (T-DM1)
echo "[1/10] NCT01772472 - Breast Cancer KATHERINE"
curl -L -o "NCT01772472_Protocol.pdf" "https://cdn.clinicaltrials.gov/large-docs/72/NCT01772472/Prot_003.pdf"
curl -L -o "NCT01772472_SAP.pdf" "https://cdn.clinicaltrials.gov/large-docs/72/NCT01772472/SAP_003.pdf"

# 2. NCT02855944 - Ovarian ARIEL4 (Rucaparib)
echo "[2/10] NCT02855944 - Ovarian ARIEL4"
curl -L -o "NCT02855944_Protocol.pdf" "https://cdn.clinicaltrials.gov/large-docs/44/NCT02855944/Prot_001.pdf"
curl -L -o "NCT02855944_SAP.pdf" "https://cdn.clinicaltrials.gov/large-docs/44/NCT02855944/SAP_001.pdf"

# 3. NCT03337724 - Breast TNBC (Ipatasertib)
echo "[3/10] NCT03337724 - Breast TNBC Ipatasertib"
curl -L -o "NCT03337724_Protocol.pdf" "https://cdn.clinicaltrials.gov/large-docs/24/NCT03337724/Prot_001.pdf"
curl -L -o "NCT03337724_SAP.pdf" "https://cdn.clinicaltrials.gov/large-docs/24/NCT03337724/SAP_001.pdf"

# 4. NCT04005716 - NSCLC (Tislelizumab)
echo "[4/10] NCT04005716 - NSCLC Tislelizumab"
curl -L -o "NCT04005716_Protocol.pdf" "https://cdn.clinicaltrials.gov/large-docs/16/NCT04005716/Prot_001.pdf"
curl -L -o "NCT04005716_SAP.pdf" "https://cdn.clinicaltrials.gov/large-docs/16/NCT04005716/SAP_001.pdf"

# 5. NCT03777657 - Esophageal (Tislelizumab)
echo "[5/10] NCT03777657 - Esophageal Tislelizumab"
curl -L -o "NCT03777657_Protocol.pdf" "https://cdn.clinicaltrials.gov/large-docs/57/NCT03777657/Prot_001.pdf"
curl -L -o "NCT03777657_SAP.pdf" "https://cdn.clinicaltrials.gov/large-docs/57/NCT03777657/SAP_001.pdf"

# 6. NCT02402062 - Neuroendocrine (SUNINET)
echo "[6/10] NCT02402062 - Neuroendocrine SUNINET"
curl -L -o "NCT02402062_Protocol.pdf" "https://cdn.clinicaltrials.gov/large-docs/62/NCT02402062/Prot_001.pdf"
curl -L -o "NCT02402062_SAP.pdf" "https://cdn.clinicaltrials.gov/large-docs/62/NCT02402062/SAP_001.pdf"

# 7. NCT01515748 - Gastric (DOS chemotherapy)
echo "[7/10] NCT01515748 - Gastric DOS"
curl -L -o "NCT01515748_Protocol.pdf" "https://cdn.clinicaltrials.gov/large-docs/48/NCT01515748/Prot_001.pdf"
curl -L -o "NCT01515748_SAP.pdf" "https://cdn.clinicaltrials.gov/large-docs/48/NCT01515748/SAP_001.pdf"

# 8. NCT04648033 - NSCLC (ARCADIAN - Oxford)
echo "[8/10] NCT04648033 - NSCLC ARCADIAN"
curl -L -o "NCT04648033_Protocol.pdf" "https://cdn.clinicaltrials.gov/large-docs/33/NCT04648033/Prot_001.pdf"
curl -L -o "NCT04648033_SAP.pdf" "https://cdn.clinicaltrials.gov/large-docs/33/NCT04648033/SAP_001.pdf"

# 9. NCT02705105 - Solid Tumors (Precision Oncology)
echo "[9/10] NCT02705105 - Solid Tumors"
curl -L -o "NCT02705105_Protocol.pdf" "https://cdn.clinicaltrials.gov/large-docs/05/NCT02705105/Prot_001.pdf"
curl -L -o "NCT02705105_SAP.pdf" "https://cdn.clinicaltrials.gov/large-docs/05/NCT02705105/SAP_001.pdf"

# 10. NCT05126433 - Solid Tumors (Lurbinectedin)
echo "[10/10] NCT05126433 - Lurbinectedin"
curl -L -o "NCT05126433_Protocol.pdf" "https://cdn.clinicaltrials.gov/large-docs/33/NCT05126433/Prot_001.pdf"
curl -L -o "NCT05126433_SAP.pdf" "https://cdn.clinicaltrials.gov/large-docs/33/NCT05126433/SAP_001.pdf"

echo ""
echo "=== Download Complete ==="
echo ""
echo "Protocol files:"
ls -lh *_Protocol.pdf 2>/dev/null || echo "No protocol files found"
echo ""
echo "SAP files:"
ls -lh *_SAP.pdf 2>/dev/null || echo "No SAP files found"
echo ""
echo "Total pairs: $(ls *_Protocol.pdf 2>/dev/null | wc -l)"
