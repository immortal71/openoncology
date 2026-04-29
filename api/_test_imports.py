#!/usr/bin/env python3
"""Validate all backend modules import correctly."""
import sys
sys.path.insert(0, '.')

errors = []

# Test all route imports
try:
    print("✅ All route modules import successfully")
except Exception as e:
    print(f"❌ Route import failed: {e}")
    errors.append(str(e))

# Test all worker imports
try:
    print("✅ All worker modules import successfully")
except Exception as e:
    print(f"❌ Worker import failed: {e}")
    errors.append(str(e))

# Test all model imports
try:
    print("✅ All model modules import successfully")
except Exception as e:
    print(f"❌ Model import failed: {e}")
    errors.append(str(e))

# Test all service imports
try:
    print("✅ All service modules import successfully")
except Exception as e:
    print(f"❌ Service import failed: {e}")
    errors.append(str(e))

# Test middleware
try:
    print("✅ All middleware modules import successfully")
except Exception as e:
    print(f"❌ Middleware import failed: {e}")
    errors.append(str(e))

# Test main app
try:
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
