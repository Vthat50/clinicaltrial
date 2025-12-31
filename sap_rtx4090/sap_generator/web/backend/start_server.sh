#!/bin/bash
# Set environment variables (use your own keys)
export SUPABASE_URL="YOUR_SUPABASE_URL"
export SUPABASE_SERVICE_KEY="YOUR_SUPABASE_SERVICE_KEY"
export ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY"

cd /mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator/web/backend
python3 main.py
