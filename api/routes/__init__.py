from routes.auth import router as auth_router
from routes.submit import router as submit_router
from routes.results import router as results_router
from routes.repurposing import router as repurposing_router
from routes.marketplace import router as marketplace_router
from routes.crowdfund import router as crowdfund_router

__all__ = [
    "auth_router", "submit_router", "results_router",
    "repurposing_router", "marketplace_router", "crowdfund_router",
]
