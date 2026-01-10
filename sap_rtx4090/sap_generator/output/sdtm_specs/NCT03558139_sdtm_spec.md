# SDTM Domain Specification

**Study ID:** NCT03558139
**Therapeutic Area:** oncology
**Total Domains:** 27
**Total Variables:** 297

---

## Required SDTM Domains

### Events

#### AE - Adverse Events

**Description:** Adverse Events domain contains data about untoward medical occurrences.
**Structure:** One record per adverse event per subject
**Justification:** Required for adverse_events, adverse_events analysis. Referenced in SAP sections: header, populations

**Selected Variables (14):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| AESEQ | Sequence Number | Num | Req |
| AETERM | Reported Term for the Adverse Event | Char | Req |
| AEDECOD | Dictionary-Derived Term | Char | Req |
| AEBODSYS | Body System or Organ Class | Char | Exp |
| AESOC | Primary System Organ Class | Char | Exp |
| AESER | Serious Event | Char | Exp |
| AEACN | Action Taken with Study Treatment | Char | Exp |
| AEREL | Causality | Char | Exp |
| AEOUT | Outcome of Adverse Event | Char | Exp |
| AESTDTC | Start Date/Time of Adverse Event | Char | Exp |
| AEENDTC | End Date/Time of Adverse Event | Char | Exp |

#### CE - Clinical Events

**Description:** Clinical Events domain for disease-related events not captured in AE.
**Structure:** One record per event per subject
**Justification:** Required based on therapeutic area standards

**Selected Variables (10):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| CESEQ | Sequence Number | Num | Req |
| CETERM | Reported Term for the Clinical Event | Char | Req |
| CEDECOD | Dictionary-Derived Term | Char | Exp |
| CESTDTC | Start Date/Time of Clinical Event | Char | Exp |
| CEENDTC | End Date/Time of Clinical Event | Char | Exp |
| VISITNUM | Visit Number | Num | Exp |
| VISIT | Visit Name | Char | Exp |

#### DD - Death Details

**Description:** Death Details captures detailed information about subject death.
**Structure:** One record per subject death
**Justification:** Required for survival, survival analysis. Referenced in SAP sections: exposure, populations

**Selected Variables (9):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| DDSEQ | Sequence Number | Num | Req |
| DDTESTCD | Death Detail Short Name | Char | Req |
| DDTEST | Death Detail Term | Char | Req |
| DDORRES | Result or Finding in Original Units | Char | Exp |
| DDSTRESC | Character Result/Finding in Std Format | Char | Exp |
| DDDTC | Date/Time of Death Assessment | Char | Exp |

#### DS - Disposition

**Description:** Disposition domain captures subject disposition and protocol milestones.
**Structure:** One record per disposition status per subject
**Justification:** Required for survival, survival analysis. Referenced in SAP sections: exposure, populations

**Selected Variables (8):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| DSSEQ | Sequence Number | Num | Req |
| DSTERM | Reported Term for the Disposition Event | Char | Req |
| DSDECOD | Standardized Disposition Term | Char | Req |
| DSCAT | Category for Disposition Event | Char | Exp |
| DSSTDTC | Start Date/Time of Disposition Event | Char | Exp |

#### DV - Protocol Deviations

**Description:** Protocol Deviations domain captures protocol deviation information.
**Structure:** One record per deviation per subject
**Justification:** Required based on therapeutic area standards

**Selected Variables (6):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| DVSEQ | Sequence Number | Num | Req |
| DVTERM | Protocol Deviation Term | Char | Req |
| DVSTDTC | Start Date/Time of Deviation | Char | Exp |

#### MH - Medical History

**Description:** Medical History domain captures subject's medical history.
**Structure:** One record per medical history event per subject
**Justification:** Required based on therapeutic area standards

**Selected Variables (8):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| MHSEQ | Sequence Number | Num | Req |
| MHTERM | Reported Term for the Medical History | Char | Req |
| MHDECOD | Dictionary-Derived Term | Char | Exp |
| MHBODSYS | Body System or Organ Class | Char | Exp |
| MHSTDTC | Start Date/Time of Medical History | Char | Exp |

### Interventions

#### CM - Concomitant Medications

**Description:** Concomitant Medications domain captures prior and concomitant medication data.
**Structure:** One record per medication per subject
**Justification:** Required for concomitant_meds analysis. Referenced in SAP sections: header

**Selected Variables (9):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| CMSEQ | Sequence Number | Num | Req |
| CMTRT | Reported Name of Drug, Med, or Therapy | Char | Req |
| CMDECOD | Standardized Medication Name | Char | Exp |
| CMINDC | Indication | Char | Exp |
| CMSTDTC | Start Date/Time of Medication | Char | Exp |
| CMENDTC | End Date/Time of Medication | Char | Exp |

#### EC - Exposure as Collected

**Description:** Exposure as Collected captures data as collected on the CRF.
**Structure:** One record per protocol-specified study treatment per subject per date
**Justification:** Required for exposure analysis. Referenced in SAP sections: exposure

**Selected Variables (13):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| ECSEQ | Sequence Number | Num | Req |
| ECTRT | Name of Treatment | Char | Req |
| ECDOSE | Dose per Administration | Num | Exp |
| ECDOSU | Dose Units | Char | Exp |
| ECDOSFRM | Dose Form | Char | Exp |
| ECROUTE | Route of Administration | Char | Exp |
| ECSTDTC | Start Date/Time of Treatment | Char | Exp |
| ECENDTC | End Date/Time of Treatment | Char | Exp |
| VISITNUM | Visit Number | Num | Exp |
| VISIT | Visit Name | Char | Exp |

#### EX - Exposure

**Description:** Exposure domain captures study treatment administration data.
**Structure:** One record per constant-dosing interval per subject
**Justification:** Required for exposure analysis. Referenced in SAP sections: exposure

**Selected Variables (12):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| EXSEQ | Sequence Number | Num | Req |
| EXTRT | Name of Treatment | Char | Req |
| EXDOSE | Dose per Administration | Num | Exp |
| EXDOSU | Dose Units | Char | Exp |
| EXDOSFRM | Dose Form | Char | Exp |
| EXDOSFRQ | Dosing Frequency per Interval | Char | Exp |
| EXROUTE | Route of Administration | Char | Exp |
| EXSTDTC | Start Date/Time of Treatment | Char | Exp |
| EXENDTC | End Date/Time of Treatment | Char | Exp |

### Special Purpose

#### CO - Comments

**Description:** Comments domain for free-text comments.
**Structure:** One record per comment per subject
**Justification:** Required based on therapeutic area standards

**Selected Variables (6):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| COSEQ | Sequence Number | Num | Req |
| COVAL | Comment | Char | Req |
| CODTC | Date/Time of Comment | Char | Exp |

#### DM - Demographics

**Description:** Demographics domain contains subject-level demographic information.
**Structure:** One record per subject
**Justification:** Required for demographics analysis. Referenced in SAP sections: demographics

**Selected Variables (22):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| SUBJID | Subject Identifier for the Study | Char | Req |
| RFSTDTC | Subject Reference Start Date/Time | Char | Exp |
| RFENDTC | Subject Reference End Date/Time | Char | Exp |
| RFXSTDTC | Date/Time of First Study Treatment | Char | Exp |
| RFXENDTC | Date/Time of Last Study Treatment | Char | Exp |
| RFICDTC | Date/Time of Informed Consent | Char | Exp |
| RFPENDTC | Date/Time of End of Participation | Char | Exp |
| DTHDTC | Date/Time of Death | Char | Exp |
| DTHFL | Subject Death Flag | Char | Exp |
| SITEID | Study Site Identifier | Char | Req |
| AGE | Age | Num | Exp |
| AGEU | Age Units | Char | Exp |
| SEX | Sex | Char | Req |
| RACE | Race | Char | Exp |
| ARMCD | Planned Arm Code | Char | Req |
| ARM | Description of Planned Arm | Char | Req |
| ACTARMCD | Actual Arm Code | Char | Exp |
| ... | *(+2 more variables)* | | |

#### SC - Subject Characteristics

**Description:** Subject Characteristics for additional subject-level data.
**Structure:** One record per characteristic per subject
**Justification:** Required for demographics analysis. Referenced in SAP sections: demographics

**Selected Variables (8):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| SCSEQ | Sequence Number | Num | Req |
| SCTESTCD | Subject Characteristic Short Name | Char | Req |
| SCTEST | Subject Characteristic | Char | Req |
| SCORRES | Result or Finding in Original Units | Char | Exp |
| SCSTRESC | Character Result/Finding in Std Format | Char | Exp |

#### SE - Subject Elements

**Description:** Subject Elements describes actual Elements through which the subject passed.
**Structure:** One record per actual Element per subject
**Justification:** Required based on therapeutic area standards

**Selected Variables (9):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| SESEQ | Sequence Number | Num | Req |
| ETCD | Element Code | Char | Req |
| ELEMENT | Description of Element | Char | Exp |
| EPOCH | Epoch | Char | Req |
| SESTDTC | Start Date/Time of Element | Char | Exp |
| SEENDTC | End Date/Time of Element | Char | Exp |

### Findings About

#### FA - Findings About

**Description:** Findings About captures additional info about Events or Interventions.
**Structure:** One record per finding about per parent record per subject
**Justification:** Required for adverse_events, adverse_events analysis. Referenced in SAP sections: header, populations

**Selected Variables (10):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| FASEQ | Sequence Number | Num | Req |
| FATESTCD | Findings About Test Short Name | Char | Req |
| FATEST | Findings About Test Name | Char | Req |
| FAOBJ | Object of Finding About | Char | Req |
| FAORRES | Result or Finding in Original Units | Char | Exp |
| FASTRESC | Character Result/Finding in Std Format | Char | Exp |
| FADTC | Date/Time of Collection | Char | Exp |

### Findings

#### IS - Immunogenicity Specimen Assessments

**Description:** Immunogenicity Specimen captures anti-drug antibody assessments.
**Structure:** One record per specimen assessment per time point per subject
**Justification:** Required based on therapeutic area standards

**Selected Variables (12):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| ISSEQ | Sequence Number | Num | Req |
| ISTESTCD | Immunogenicity Test Short Name | Char | Req |
| ISTEST | Immunogenicity Test Name | Char | Req |
| ISORRES | Result or Finding in Original Units | Char | Exp |
| ISSTRESC | Character Result/Finding in Std Format | Char | Exp |
| ISSPEC | Specimen Material Type | Char | Exp |
| ISDTC | Date/Time of Specimen Collection | Char | Exp |
| VISITNUM | Visit Number | Num | Exp |
| VISIT | Visit Name | Char | Exp |

#### LB - Laboratory Test Results

**Description:** Laboratory Test Results domain captures central and local lab data.
**Structure:** One record per lab test per time point per subject
**Justification:** Required for laboratory, laboratory analysis. Referenced in SAP sections: header, populations

**Selected Variables (20):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| LBSEQ | Sequence Number | Num | Req |
| LBTESTCD | Lab Test or Examination Short Name | Char | Req |
| LBTEST | Lab Test or Examination Name | Char | Req |
| LBCAT | Category for Lab Test | Char | Exp |
| LBORRES | Result or Finding in Original Units | Char | Exp |
| LBORRESU | Original Units | Char | Exp |
| LBORNRLO | Reference Range Lower Limit in Orig Unit | Char | Exp |
| LBORNRHI | Reference Range Upper Limit in Orig Unit | Char | Exp |
| LBSTRESC | Character Result/Finding in Std Format | Char | Exp |
| LBSTRESN | Numeric Result/Finding in Standard Units | Num | Exp |
| LBSTRESU | Standard Units | Char | Exp |
| LBSTNRLO | Reference Range Lower Limit-Std Units | Num | Exp |
| LBSTNRHI | Reference Range Upper Limit-Std Units | Num | Exp |
| LBNRIND | Reference Range Indicator | Char | Exp |
| LBDTC | Date/Time of Specimen Collection | Char | Exp |
| VISITNUM | Visit Number | Num | Exp |
| VISIT | Visit Name | Char | Exp |

#### PC - Pharmacokinetic Concentrations

**Description:** PK Concentrations domain captures drug concentration measurements.
**Structure:** One record per concentration per time point per subject
**Justification:** Required for pharmacokinetics analysis. Referenced in SAP sections: pk

**Selected Variables (20):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| PCSEQ | Sequence Number | Num | Req |
| PCTESTCD | PK Concentration Test Short Name | Char | Req |
| PCTEST | PK Concentration Test Name | Char | Req |
| PCORRES | Result or Finding in Original Units | Char | Exp |
| PCORRESU | Original Units | Char | Exp |
| PCSTRESC | Character Result/Finding in Std Format | Char | Exp |
| PCSTRESN | Numeric Result/Finding in Standard Units | Num | Exp |
| PCSTRESU | Standard Units | Char | Exp |
| PCSPEC | Specimen Material Type | Char | Exp |
| PCDTC | Date/Time of Specimen Collection | Char | Exp |
| PCTPT | Planned Time Point Name | Char | Exp |
| PCTPTNUM | Planned Time Point Number | Num | Exp |
| PCELTM | Planned Elapsed Time from Time Point Ref | Char | Exp |
| PCTPTREF | Time Point Reference | Char | Exp |
| PCRFTDTC | Date/Time of Reference Time Point | Char | Exp |
| VISITNUM | Visit Number | Num | Exp |
| VISIT | Visit Name | Char | Exp |

#### PP - Pharmacokinetic Parameters

**Description:** PK Parameters domain captures derived PK parameters.
**Structure:** One record per PK parameter per subject
**Justification:** Required for pharmacokinetics analysis. Referenced in SAP sections: pk

**Selected Variables (14):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| PPSEQ | Sequence Number | Num | Req |
| PPTESTCD | PK Parameter Short Name | Char | Req |
| PPTEST | PK Parameter Name | Char | Req |
| PPORRES | Result or Finding in Original Units | Char | Exp |
| PPORRESU | Original Units | Char | Exp |
| PPSTRESC | Character Result/Finding in Std Format | Char | Exp |
| PPSTRESN | Numeric Result/Finding in Standard Units | Num | Exp |
| PPSTRESU | Standard Units | Char | Exp |
| PPRFTDTC | Date/Time of Reference Point | Char | Exp |
| VISITNUM | Visit Number | Num | Exp |
| VISIT | Visit Name | Char | Exp |

#### QS - Questionnaires

**Description:** Questionnaires domain captures PRO and clinician-reported outcomes.
**Structure:** One record per questionnaire item per time point per subject
**Justification:** Required for questionnaire, questionnaire analysis. Referenced in SAP sections: header, endpoints

**Selected Variables (13):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| QSSEQ | Sequence Number | Num | Req |
| QSTESTCD | Questionnaire Item Short Name | Char | Req |
| QSTEST | Questionnaire Item Name | Char | Req |
| QSCAT | Category of Questionnaire | Char | Req |
| QSORRES | Result or Finding in Original Units | Char | Exp |
| QSSTRESC | Character Result/Finding in Std Format | Char | Exp |
| QSSTRESN | Numeric Result/Finding in Standard Units | Num | Exp |
| QSDTC | Date/Time of Finding | Char | Exp |
| VISITNUM | Visit Number | Num | Exp |
| VISIT | Visit Name | Char | Exp |

#### RS - Disease Response

**Description:** Disease Response domain captures tumor response assessments.
**Structure:** One record per response assessment per time point per subject
**Justification:** Required for tumor_response analysis. Referenced in SAP sections: objectives

**Selected Variables (13):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| RSSEQ | Sequence Number | Num | Req |
| RSTESTCD | Disease Response Short Name | Char | Req |
| RSTEST | Disease Response Test Name | Char | Req |
| RSCAT | Category for Disease Response | Char | Exp |
| RSORRES | Result or Finding in Original Units | Char | Exp |
| RSSTRESC | Character Result/Finding in Std Format | Char | Exp |
| RSEVAL | Evaluator | Char | Exp |
| RSDTC | Date/Time of Disease Response | Char | Exp |
| VISITNUM | Visit Number | Num | Exp |
| VISIT | Visit Name | Char | Exp |

#### TR - Tumor Results

**Description:** Tumor Results domain captures tumor identification and measurements.
**Structure:** One record per tumor assessment per time point per subject
**Justification:** Required for tumor_response analysis. Referenced in SAP sections: objectives

**Selected Variables (17):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| TRSEQ | Sequence Number | Num | Req |
| TRLNKID | Link ID | Char | Exp |
| TRTESTCD | Tumor/Lesion Assessment Short Name | Char | Req |
| TRTEST | Tumor/Lesion Assessment Test Name | Char | Req |
| TRORRES | Result or Finding in Original Units | Char | Exp |
| TRORRESU | Original Units | Char | Exp |
| TRSTRESC | Character Result/Finding in Std Format | Char | Exp |
| TRSTRESN | Numeric Result/Finding in Standard Units | Num | Exp |
| TRSTRESU | Standard Units | Char | Exp |
| TRMETHOD | Method of Test | Char | Exp |
| TREVAL | Evaluator | Char | Exp |
| TRDTC | Date/Time of Assessment | Char | Exp |
| VISITNUM | Visit Number | Num | Exp |
| VISIT | Visit Name | Char | Exp |

#### TU - Tumor Identification

**Description:** Tumor Identification domain captures tumor/lesion characteristics.
**Structure:** One record per tumor identified per subject
**Justification:** Required for tumor_response analysis. Referenced in SAP sections: objectives

**Selected Variables (16):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| USUBJID | Unique Subject Identifier | Char | Req |
| TUSEQ | Sequence Number | Num | Req |
| TULNKID | Link ID | Char | Req |
| TUTESTCD | Tumor/Lesion ID Short Name | Char | Req |
| TUTEST | Tumor/Lesion ID Test Name | Char | Req |
| TUORRES | Result or Finding in Original Units | Char | Exp |
| TUSTRESC | Character Result/Finding in Std Format | Char | Exp |
| TULOC | Location of Tumor/Lesion | Char | Exp |
| TUMETHOD | Method of Identification | Char | Exp |
| TUEVAL | Evaluator | Char | Exp |
| TUDTC | Date/Time of Identification | Char | Exp |
| VISITNUM | Visit Number | Num | Exp |
| VISIT | Visit Name | Char | Exp |
| TUDY | Study Day of Identification | Num | Perm |

### Relationship

#### RELREC - Related Records

**Description:** Related Records domain links records between domains.
**Structure:** One record per related record relationship
**Justification:** Required based on therapeutic area standards

**Selected Variables (4):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| RDOMAIN | Related Domain Abbreviation | Char | Req |
| IDVAR | Identifying Variable | Char | Req |
| IDVARVAL | Identifying Variable Value | Char | Req |

### Trial Design

#### TA - Trial Arms

**Description:** Trial Arms domain describes each planned Arm in the trial.
**Structure:** One record per planned Element per Arm
**Justification:** Required for trial design documentation

**Selected Variables (8):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| ARMCD | Planned Arm Code | Char | Req |
| ARM | Description of Planned Arm | Char | Req |
| TAETORD | Planned Order of Element within Arm | Num | Req |
| ETCD | Element Code | Char | Req |
| ELEMENT | Description of Element | Char | Req |
| EPOCH | Epoch | Char | Req |

#### TE - Trial Elements

**Description:** Trial Elements domain describes basic building blocks of trial design.
**Structure:** One record per planned Element
**Justification:** Required for trial design documentation

**Selected Variables (4):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| ETCD | Element Code | Char | Req |
| ELEMENT | Description of Element | Char | Req |

#### TS - Trial Summary

**Description:** Trial Summary domain describes overall trial information.
**Structure:** One record per trial summary parameter value
**Justification:** Required for trial design documentation

**Selected Variables (6):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| TSSEQ | Sequence Number | Num | Req |
| TSPARMCD | Trial Summary Parameter Short Name | Char | Req |
| TSPARM | Trial Summary Parameter | Char | Req |
| TSVAL | Parameter Value | Char | Req |

#### TV - Trial Visits

**Description:** Trial Visits domain describes planned study visits.
**Structure:** One record per planned Visit per Arm
**Justification:** Required for trial design documentation

**Selected Variables (6):**

| Variable | Label | Type | Core |
|----------|-------|------|------|
| STUDYID | Study Identifier | Char | Req |
| DOMAIN | Domain Abbreviation | Char | Req |
| VISITNUM | Visit Number | Num | Req |
| VISIT | Visit Name | Char | Req |
| ARMCD | Planned Arm Code | Char | Req |
| ARM | Description of Planned Arm | Char | Perm |

---

## Data Requirements Extracted from SAP

### Adverse Events

**Source Section:** header
**Mapped Domains:** AE, FA

### Laboratory

**Source Section:** header
**Mapped Domains:** LB

### Questionnaire

**Source Section:** header
**Mapped Domains:** QS

### Concomitant Meds

**Source Section:** header
**Mapped Domains:** CM

### Tumor Response

**Source Section:** objectives
**Mapped Domains:** RS, TR, TU

### Questionnaire

**Source Section:** endpoints
**Mapped Domains:** QS

### Adverse Events

**Source Section:** populations
**Mapped Domains:** AE, FA

### Laboratory

**Source Section:** populations
**Mapped Domains:** LB

### Survival

**Source Section:** populations
**Mapped Domains:** DS, DD

### Pharmacokinetics

**Source Section:** pk
**Mapped Domains:** PC, PP

### Demographics

**Source Section:** demographics
**Mapped Domains:** DM, SC

### Survival

**Source Section:** exposure
**Mapped Domains:** DS, DD

### Exposure

**Source Section:** exposure
**Mapped Domains:** EX, EC
