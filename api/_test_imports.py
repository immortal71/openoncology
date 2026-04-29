#!/usr/bin/env python3
"""Validate all backend modules import correctly."""
import sys
sys.path.insert(0, '.')

errors = []

# Test all route imports
try:
    import routes.auth as routes_auth
    import routes.submit as routes_submit
    import routes.results as routes_results
    import routes.repurposing as routes_repurposing
    import routes.marketplace as routes_marketplace
    import routes.oncologist as routes_oncologist
    import routes.webhook as routes_webhook
    import routes.pharma_admin as routes_pharma_admin
    import routes.stripe_connect as routes_stripe_connect
    import routes.campaign as routes_campaign
    import routes.gdpr as routes_gdpr
    assert routes_auth is not None
    assert routes_submit is not None
    assert routes_results is not None
    assert routes_repurposing is not None
    assert routes_marketplace is not None
    assert routes_oncologist is not None
    assert routes_webhook is not None
    assert routes_pharma_admin is not None
    assert routes_stripe_connect is not None
    assert routes_campaign is not None
    assert routes_gdpr is not None
    print("\u2705 All route modules import successfully")
except Exception as e:
    print(f"\u274c Route import failed: {e}")
    errors.append(str(e))

# Test all worker imports
try:
    import workers.ai_worker as ai_worker
    import workers.genomic_worker as genomic_worker
    import workers.gdpr_worker as gdpr_worker
    import workers.notify_worker as notify_worker
    assert ai_worker is not None
    assert genomic_worker is not None
    assert gdpr_worker is not None
    assert notify_worker is not None
    print("\u2705 All worker modules import successfully")
except Exception as e:
    print(f"\u274c Worker import failed: {e}")
    errors.append(str(e))

# Test all model imports
try:
    import models.patient as models_patient
    import models.submission as models_submission
    import models.mutation as models_mutation
    import models.result as models_result
    import models.repurposing as models_repurposing
    import models.campaign as models_campaign
    import models.order as models_order
    import models.pharma as models_pharma
    import models.bid as models_bid
    import models.deletion_request as models_deletion_request
    import models.oncologist as models_oncologist
    assert models_patient is not None
    assert models_submission is not None
    assert models_mutation is not None
    assert models_result is not None
    assert models_repurposing is not None
    assert models_campaign is not None
    assert models_order is not None
    assert models_pharma is not None
    assert models_bid is not None
    assert models_deletion_request is not None
    assert models_oncologist is not None
    print("\u2705 All model modules import successfully")
except Exception as e:
    print(f"\u274c Model import failed: {e}")
    errors.append(str(e))

# Test all service imports
try:
    import services.cbioportal as svc_cbioportal
    import services.chembl as svc_chembl
    import services.civic as svc_civic
    import services.clinvar as svc_clinvar
    import services.cosmic as svc_cosmic
    import services.email_templates as svc_email_templates
    import services.llm_explainer as svc_llm_explainer
    import services.oncokb as svc_oncokb
    import services.opentargets as svc_opentargets
    import services.storage as svc_storage
    assert svc_cbioportal is not None
    assert svc_chembl is not None
    assert svc_civic is not None
    assert svc_clinvar is not None
    assert svc_cosmic is not None
    assert svc_email_templates is not None
    assert svc_llm_explainer is not None
    assert svc_oncokb is not None
    assert svc_opentargets is not None
    assert svc_storage is not None
    print("\u2705 All service modules import successfully")
except Exception as e:
    print(f"\u274c Service import failed: {e}")
    errors.append(str(e))

# Test middleware
try:
    import middleware.audit as mw_audit
    import middleware.rate_limit as mw_rate_limit
    assert mw_audit is not None
    assert mw_rate_limit is not None
    print("\u2705 All middleware modules import successfully")
except Exception as e:
    print(f"\u274c Middleware import failed: {e}")
    errors.append(str(e))

# Test main app
try:
    import main as main_module
    assert main_module.app is not None
    print("\u2705 Main app imports successfully")
except Exception as e:
    print(f"\u274c Main app import failed: {e}")
    errors.append(str(e))

if errors:
    print(f"\n\u274c {len(errors)} errors encountered")
    sys.exit(1)
else:
    print("\n\u2705 ALL BACKEND MODULES VALIDATED SUCCESSFULLY!")
    sys.exit(0)
