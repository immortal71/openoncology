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
    _ = (routes_auth, routes_submit, routes_results, routes_repurposing,
         routes_marketplace, routes_oncologist, routes_webhook, routes_pharma_admin,
         routes_stripe_connect, routes_campaign, routes_gdpr)
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
    _ = (ai_worker, genomic_worker, gdpr_worker, notify_worker)
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
    _ = (models_patient, models_submission, models_mutation, models_result,
         models_repurposing, models_campaign, models_order, models_pharma,
         models_bid, models_deletion_request, models_oncologist)
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
    _ = (svc_cbioportal, svc_chembl, svc_civic, svc_clinvar, svc_cosmic,
         svc_email_templates, svc_llm_explainer, svc_oncokb, svc_opentargets, svc_storage)
    print("\u2705 All service modules import successfully")
except Exception as e:
    print(f"\u274c Service import failed: {e}")
    errors.append(str(e))

# Test middleware
try:
    import middleware.audit as mw_audit
    import middleware.rate_limit as mw_rate_limit
    _ = (mw_audit, mw_rate_limit)
    print("\u2705 All middleware modules import successfully")
except Exception as e:
    print(f"\u274c Middleware import failed: {e}")
    errors.append(str(e))

# Test main app
try:
    import main as main_module
    _ = main_module.app
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
