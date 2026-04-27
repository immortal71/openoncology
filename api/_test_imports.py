#!/usr/bin/env python3
"""Validate all backend modules import correctly."""
import sys
sys.path.insert(0, '.')

errors = []

# Test all route imports
try:
    from routes import auth, submit, results, repurposing, marketplace, oncologist, webhook, pharma_admin, stripe_connect, campaign, gdpr
    print("✅ All route modules import successfully")
except Exception as e:
    print(f"❌ Route import failed: {e}")
    errors.append(str(e))

# Test all worker imports
try:
    from workers import ai_worker, genomic_worker, gdpr_worker, notify_worker
    print("✅ All worker modules import successfully")
except Exception as e:
    print(f"❌ Worker import failed: {e}")
    errors.append(str(e))

# Test all model imports
try:
    from models import patient, submission, mutation, result, repurposing, campaign, order, pharma, bid, deletion_request, oncologist
    print("✅ All model modules import successfully")
except Exception as e:
    print(f"❌ Model import failed: {e}")
    errors.append(str(e))

# Test all service imports
try:
    from services import cbioportal, chembl, civic, clinvar, cosmic, email_templates, llm_explainer, oncokb, opentargets, storage
    print("✅ All service modules import successfully")
except Exception as e:
    print(f"❌ Service import failed: {e}")
    errors.append(str(e))

# Test middleware
try:
    from middleware import audit, rate_limit
    print("✅ All middleware modules import successfully")
except Exception as e:
    print(f"❌ Middleware import failed: {e}")
    errors.append(str(e))

# Test main app
try:
    from main import app
    print("✅ Main app imports successfully")
except Exception as e:
    print(f"❌ Main app import failed: {e}")
    errors.append(str(e))

if errors:
    print(f"\n❌ {len(errors)} errors encountered")
    sys.exit(1)
else:
    print("\n✅ ALL BACKEND MODULES VALIDATED SUCCESSFULLY!")
    sys.exit(0)
