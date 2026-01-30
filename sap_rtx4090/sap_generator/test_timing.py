#!/usr/bin/env python3
"""Quick timing test to find bottlenecks."""
import time
import os
os.chdir("/mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator")

# Simple test protocol
TEST_PROTOCOL = """
NCT12345678 - Phase 3 Study
Drug: Pembrolizumab
Indication: NSCLC
Sample Size: 500 patients (1:1 randomization)
Primary Endpoint: Overall Survival
Statistical Method: Stratified log-rank test
One interim analysis at 60% information fraction
Lan-DeMets O'Brien-Fleming spending function
"""

print("=" * 50)
print("TIMING TEST")
print("=" * 50)

# Test 1: LLM client initialization
t0 = time.time()
from enterprise_sap_system.core.tiered_llm import TieredLLMClient
llm = TieredLLMClient()
print(f"\n1. LLM init: {time.time()-t0:.1f}s")

# Test 2: Single LLM call
t0 = time.time()
resp = llm.chat("Say 'hello' in one word", max_tokens=10)
print(f"2. Single LLM call: {time.time()-t0:.1f}s")

# Test 3: Parallel LLM calls (simulate extraction)
from concurrent.futures import ThreadPoolExecutor, as_completed
t0 = time.time()
def call_llm(i):
    return llm.chat(f"Say the number {i}", max_tokens=10)

with ThreadPoolExecutor(max_workers=5) as ex:
    futures = [ex.submit(call_llm, i) for i in range(5)]
    for f in as_completed(futures):
        f.result()
print(f"3. Parallel LLM (5 calls): {time.time()-t0:.1f}s")

# Test 4: ChromaDB query
t0 = time.time()
try:
    from enterprise_sap_system.rag.vector_store import create_vector_store
    rag = create_vector_store()
    results = rag.query("methods", "overall survival log-rank", n_results=3)
    print(f"4. ChromaDB query: {time.time()-t0:.1f}s")
except Exception as e:
    print(f"4. ChromaDB query: FAILED ({e})")

print("\n" + "=" * 50)
print("If step 3 takes much longer than 5x step 2,")
print("rate limiting is the bottleneck.")
print("=" * 50)
