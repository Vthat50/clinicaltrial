# System Comparison: KG Pipeline vs Main Production Pipeline

## Architecture Overview

### Main Production Pipeline (`ProductionSAPPipeline`)
```
Protocol → Sectioned Extraction → Knowledge Graph Context → RAG Style → Generation → SELF-RAG Verification
```

**Components:**
- `SectionedProtocolExtractor` - Structured fact extraction with confidence scores
- `TwoPassExtractor` - Two-pass extraction for completeness
- `TieredLLMClient` - Claude → OpenAI → Groq fallback chain
- `RAGSanitizer` - Strips numbers from RAG examples (prose style only)
- `FactVerifier` - SELF-RAG verification with reflection tokens
- `OncologyDecisionEngine` - Oncology-specific rules
- `SAPValidator` - Strict validation
- `KnowledgeRuleEngine` - ICH E9, FDA guidance context
- **ChromaDB Vector Store** - 326 SAPs indexed, 352 sections

**Sections Generated:** 12 sections per ICH E9 R1 + Gamble et al. 2017

### KG Pipeline (`ClaudeKGPipeline`)
```
Protocol → Claude Entity Extraction → KG Context Query → Claude Generation
```

**Components:**
- `ClaudeKGExtractor` - Single-pass entity extraction
- `FactualKnowledgeGraphV2` - 2,840 nodes, 3,161 edges
- `ClaudeSAPGenerator` - Direct Claude generation with facts + context

---

## Feature Comparison

| Feature | Main Production | KG Pipeline | Winner |
|---------|-----------------|-------------|--------|
| **Extraction Method** | Sectioned + Two-pass | Single Claude call | Main (more thorough) |
| **LLM Fallbacks** | Claude → OpenAI → Groq | Claude only | Main (more robust) |
| **Verification** | SELF-RAG with correction loop | None | Main |
| **RAG Context** | 326 SAPs, sanitized | 5 similar trial facts | Main (richer context) |
| **Knowledge Graph** | ICH E9, FDA guidance | 2,840 factual nodes | Tie |
| **Provenance** | Partial | Full (source tags + quotes) | KG |
| **Transparency** | No inferred markers | `[INFERRED]` markers | KG |
| **Complexity** | ~100K lines, many dependencies | ~500 lines, minimal deps | KG |
| **Speed** | Slower (multi-pass) | Faster (single-pass) | KG |
| **Section Coverage** | 12 standard sections | 12 sections + TLF shells | Tie |

---

## Accuracy Comparison (Against Real SAP)

Based on NCT03558139 comparison:

| Category | KG Pipeline Score | Main Pipeline (Expected) |
|----------|-------------------|--------------------------|
| Endpoints | 95% | ~95% (same source) |
| Study Design | 100% | ~100% (same source) |
| Analysis Sets | 80% | ~90% (more rules) |
| Statistical Methods | 75% | ~85% (RAG examples) |
| Version Specifics | 50% | ~70% (RAG has versions) |
| Power Calculations | 30% | ~60% (boundary calculator) |
| Safety Details | 70% | ~75% (structured extraction) |
| **Overall** | **73%** | **~80-85%** |

---

## Key Differences

### Main Pipeline Strengths:
1. **Verification loop** - SELF-RAG catches hallucinations
2. **Richer RAG context** - 326 real SAPs for style/structure
3. **Boundary calculator** - Actual power/sample size calculations
4. **Structured extraction** - More reliable fact extraction
5. **Multi-tier LLM** - Fallbacks prevent failures

### KG Pipeline Strengths:
1. **Full provenance** - Every fact traced to source quote
2. **Transparency** - `[INFERRED]` markers show assumptions
3. **Simplicity** - 500 lines vs 100K+ lines
4. **Speed** - Single Claude call vs multi-pass
5. **Factual KG** - 2,840 verified facts from 20+ SAPs

---

## Verdict

### Main Pipeline is Better For:
- **Production use** - More robust with fallbacks and verification
- **Regulatory submissions** - Boundary calculations matter
- **Complex trials** - Multi-pass extraction catches edge cases
- **Style consistency** - RAG provides real SAP prose patterns

### KG Pipeline is Better For:
- **Transparency/Auditability** - Every fact has provenance
- **Rapid prototyping** - Faster, simpler architecture
- **Debugging** - Easy to see what was extracted vs inferred
- **Training data** - Clear source attribution for ML pipelines

---

## Recommendation

**Hybrid Approach:** Combine both systems:

1. Use **KG Pipeline** for:
   - Initial fact extraction with provenance
   - `[INFERRED]` marking for manual review flags
   - Factual knowledge graph context

2. Use **Main Pipeline** for:
   - SELF-RAG verification loop
   - RAG-based prose style refinement
   - Boundary/power calculations
   - Multi-tier LLM robustness

**Proposed Integration:**
```
Protocol
  → KG Extraction (with provenance)
  → Main Pipeline Verification (SELF-RAG)
  → RAG Style Polishing
  → Boundary Calculations
  → Final SAP with full audit trail
```

This would give ~85% accuracy with full provenance tracking.
