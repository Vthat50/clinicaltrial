# Oncology Protocols & SAPs - CLEAR BREAKDOWN

## The Reality of ClinicalTrials.gov Documents

**What ClinicalTrials.gov provides:**
- `Prot_SAP_XXX.pdf` = Protocol AND SAP combined in ONE file
- `Prot_XXX.pdf` = Protocol ONLY
- `SAP_XXX.pdf` = SAP ONLY

**What YOU need for training:** Separate files:
- Protocol (input) → SAP (output)

---

## BEST FOR TRAINING: Trials with SEPARATE Protocol AND SAP Files

These are rare but ideal. You get the protocol as input, SAP as output:

| NCT | Cancer | Protocol File | SAP File | Notes |
|-----|--------|---------------|----------|-------|
| NCT01772472 | Breast (HER2+) | Prot_003.pdf | SAP_003.pdf | KATHERINE - T-DM1 trial |
| NCT02855944 | Ovarian (BRCA) | Prot_001.pdf | SAP_001.pdf | ARIEL4 - Rucaparib |
| NCT03337724 | Breast (TNBC) | Prot_001.pdf | SAP_001.pdf | Ipatasertib - Roche |
| NCT04005716 | NSCLC | Prot_001.pdf | SAP_001.pdf | Tislelizumab - BeiGene |
| NCT03777657 | Esophageal | Prot_001.pdf | SAP_001.pdf | Tislelizumab |
| NCT02402062 | Neuroendocrine | Prot_001.pdf | SAP_001.pdf | SUNINET trial |
| NCT01515748 | Gastric | Prot_001.pdf | SAP_001.pdf | DOS chemotherapy |
| NCT04648033 | NSCLC | Prot_001.pdf | SAP_001.pdf | ARCADIAN - Oxford |
| NCT02705105 | Solid Tumors | Prot_001.pdf | SAP_001.pdf | Precision Oncology |
| NCT05126433 | Solid Tumors | Prot_001.pdf | SAP_001.pdf | Lurbinectedin - Jazz |

### Download URLs for Separate Files

```bash
# NCT01772472 - Breast Cancer KATHERINE
curl -L -o NCT01772472_Protocol.pdf "https://cdn.clinicaltrials.gov/large-docs/72/NCT01772472/Prot_003.pdf"
curl -L -o NCT01772472_SAP.pdf "https://cdn.clinicaltrials.gov/large-docs/72/NCT01772472/SAP_003.pdf"

# NCT02855944 - Ovarian ARIEL4
curl -L -o NCT02855944_Protocol.pdf "https://cdn.clinicaltrials.gov/large-docs/44/NCT02855944/Prot_001.pdf"
curl -L -o NCT02855944_SAP.pdf "https://cdn.clinicaltrials.gov/large-docs/44/NCT02855944/SAP_001.pdf"

# NCT03337724 - Breast TNBC Ipatasertib
curl -L -o NCT03337724_Protocol.pdf "https://cdn.clinicaltrials.gov/large-docs/24/NCT03337724/Prot_001.pdf"
curl -L -o NCT03337724_SAP.pdf "https://cdn.clinicaltrials.gov/large-docs/24/NCT03337724/SAP_001.pdf"

# NCT04005716 - NSCLC Tislelizumab
curl -L -o NCT04005716_Protocol.pdf "https://cdn.clinicaltrials.gov/large-docs/16/NCT04005716/Prot_001.pdf"
curl -L -o NCT04005716_SAP.pdf "https://cdn.clinicaltrials.gov/large-docs/16/NCT04005716/SAP_001.pdf"

# NCT03777657 - Esophageal Tislelizumab
curl -L -o NCT03777657_Protocol.pdf "https://cdn.clinicaltrials.gov/large-docs/57/NCT03777657/Prot_001.pdf"
curl -L -o NCT03777657_SAP.pdf "https://cdn.clinicaltrials.gov/large-docs/57/NCT03777657/SAP_001.pdf"

# NCT02402062 - Neuroendocrine SUNINET
curl -L -o NCT02402062_Protocol.pdf "https://cdn.clinicaltrials.gov/large-docs/62/NCT02402062/Prot_001.pdf"
curl -L -o NCT02402062_SAP.pdf "https://cdn.clinicaltrials.gov/large-docs/62/NCT02402062/SAP_001.pdf"

# NCT01515748 - Gastric DOS
curl -L -o NCT01515748_Protocol.pdf "https://cdn.clinicaltrials.gov/large-docs/48/NCT01515748/Prot_001.pdf"
curl -L -o NCT01515748_SAP.pdf "https://cdn.clinicaltrials.gov/large-docs/48/NCT01515748/SAP_001.pdf"

# NCT04648033 - NSCLC ARCADIAN
curl -L -o NCT04648033_Protocol.pdf "https://cdn.clinicaltrials.gov/large-docs/33/NCT04648033/Prot_001.pdf"
curl -L -o NCT04648033_SAP.pdf "https://cdn.clinicaltrials.gov/large-docs/33/NCT04648033/SAP_001.pdf"

# NCT02705105 - Solid Tumors
curl -L -o NCT02705105_Protocol.pdf "https://cdn.clinicaltrials.gov/large-docs/05/NCT02705105/Prot_001.pdf"
curl -L -o NCT02705105_SAP.pdf "https://cdn.clinicaltrials.gov/large-docs/05/NCT02705105/SAP_001.pdf"

# NCT05126433 - Lurbinectedin
curl -L -o NCT05126433_Protocol.pdf "https://cdn.clinicaltrials.gov/large-docs/33/NCT05126433/Prot_001.pdf"
curl -L -o NCT05126433_SAP.pdf "https://cdn.clinicaltrials.gov/large-docs/33/NCT05126433/SAP_001.pdf"
```

---

## COMBINED FILES (Protocol + SAP in same PDF)

These are useful for understanding format but need manual splitting:

| NCT | Cancer | File | Size |
|-----|--------|------|------|
| NCT02763579 | SCLC | Prot_SAP_000.pdf | ~200 pages |
| NCT03036098 | Bladder | Prot_SAP_000.pdf | ~300 pages |
| NCT02362594 | Melanoma | Prot_SAP_000.pdf | ~250 pages |
| NCT02500797 | Sarcoma | Prot_SAP_000.pdf | ~150 pages |
| NCT02339740 | Pediatric APL | Prot_SAP_000.pdf | ~200 pages |
| NCT04396860 | Glioblastoma | Prot_SAP_001.pdf | ~250 pages |

---

## HOW TO FIND MORE SEPARATE FILES

### Method 1: AACT Database Query

```sql
-- Connect to AACT: aact-db.ctti-clinicaltrials.org
-- Find oncology trials with separate protocol AND SAP files

SELECT DISTINCT 
    s.nct_id,
    s.brief_title,
    s.phase,
    d.document_type,
    d.url
FROM studies s
JOIN documents d ON s.nct_id = d.nct_id
JOIN conditions c ON s.nct_id = c.nct_id
WHERE 
    c.downcase_name LIKE '%cancer%' 
    OR c.downcase_name LIKE '%carcinoma%'
    OR c.downcase_name LIKE '%lymphoma%'
    OR c.downcase_name LIKE '%leukemia%'
    OR c.downcase_name LIKE '%melanoma%'
    OR c.downcase_name LIKE '%sarcoma%'
AND s.phase IN ('Phase 3', 'Phase 2/Phase 3')
AND s.nct_id IN (
    -- Has protocol
    SELECT nct_id FROM documents WHERE document_type = 'Study Protocol'
    INTERSECT
    -- Also has SAP
    SELECT nct_id FROM documents WHERE document_type = 'Statistical Analysis Plan'
)
ORDER BY s.nct_id;
```

### Method 2: Manual ClinicalTrials.gov Search

1. Go to: https://clinicaltrials.gov/search
2. Add filters:
   - Condition: Cancer (or specific type)
   - Phase: Phase 3
   - Study Documents: Has Protocol, Has SAP
   - Status: Completed
3. Look at each result's "Study Documents" section
4. Look for trials that list BOTH "Study Protocol" AND "Statistical Analysis Plan" as separate entries

---

## SUMMARY FOR YOUR BUILD

**For your 4-day sprint, use these 10 trials with SEPARATE files:**

1. NCT01772472 (Breast - KATHERINE)
2. NCT02855944 (Ovarian - ARIEL4)
3. NCT03337724 (Breast TNBC)
4. NCT04005716 (NSCLC)
5. NCT03777657 (Esophageal)
6. NCT02402062 (Neuroendocrine)
7. NCT01515748 (Gastric)
8. NCT04648033 (NSCLC)
9. NCT02705105 (Solid Tumors)
10. NCT05126433 (Solid Tumors)

**Total: 10 Protocol-SAP pairs** - enough to start development and test your pipeline.

For production, you'll need 100-500+ pairs. Use the AACT query above to find more.

---

## TEMPLATE FILES

There are NO public SAP templates in ClinicalTrials.gov. 

For templates, look at:
- TransCelerate SAP template: https://www.transceleratebiopharmainc.com/
- ICH E9 guidelines for SAP structure
- CONSORT-related statistical guidance
