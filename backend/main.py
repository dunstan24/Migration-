"""
main.py — FastAPI entry point
Models loaded at startup via lifespan:
  models["pathway"]     — GBM sklearn Pipeline     backend/models/model_a.joblib
  models["approval"]    — XGBoost XGBClassifier     backend/models/model_xgboost.json
  models["occ_encoder"] — sklearn LabelEncoder      backend/models/encoder_occupation.joblib
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging, os, sys, numpy as np
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from config import settings
from db.database import init_db
import db.models  # Ensure models are registered for init_db

# ── Sentry Initialization ─────────────────────────────────────
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENV,
        integrations=[FastApiIntegration()],
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of transactions.
        profiles_sample_rate=1.0,
    )


def configure_console_output():
    """Ensure emoji and other Unicode output do not crash Windows terminals."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


configure_console_output()

# Use uvicorn.error logger to ensure messages show up in the console
api_logger = logging.getLogger("uvicorn.error")
models = {}


def _patch_sklearn_imputer():
    """Fix sklearn SimpleImputer compatibility (trained on ~1.2, running on 1.4+)."""
    try:
        from sklearn.impute import SimpleImputer
        if not hasattr(SimpleImputer, "_fill_dtype"):
            def _fill_dtype(self):
                if (self.statistics_ is not None
                        and self.statistics_.dtype.kind in ("U","O","S")):
                    return object
                return np.float64
            SimpleImputer._fill_dtype = property(_fill_dtype)
            api_logger.info("Applied sklearn SimpleImputer compatibility patch")
    except Exception as e:
        api_logger.warning(f"Could not apply sklearn patch: {e}")


def _load_joblib(path: str, label: str):
    import joblib
    import traceback
    if not os.path.exists(path):
        api_logger.warning(f"{label} not found at {path}")
        return None
    try:
        print(f"DEBUG: Attempting to load {label} from {path}...")
        obj = joblib.load(path)
        api_logger.info(f"Loaded {label} ({path}) ✓")
        return obj
    except Exception as e:
        api_logger.error(f"Failed to load {label}: {e}")
        # Print traceback to console for deep debugging
        traceback.print_exc()
        return None


def _load_pickle(path: str, label: str):
    import pickle
    if not os.path.exists(path):
        api_logger.warning(f"{label} not found at {path}")
        return None
    try:
        with open(path, "rb") as f:
            obj = pickle.load(f)
        api_logger.info(f"Loaded {label} ({path})")
        return obj
    except Exception as e:
        api_logger.error(f"Failed to load {label}: {e}")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    _patch_sklearn_imputer()

    # Use absolute-relative path for reliability
    models_dir = os.path.join(os.path.dirname(__file__), "models")

    # ── Lazy Loading Helper ───────────────────────────────────
    # We define it here or as a global, but we populate 'models' dict
    
    def load_all_models():
        # GBM pathway model (sklearn Pipeline)
        models["pathway"] = _load_joblib(
            os.path.join(models_dir, "model_a.joblib"), "pathway model"
        )

        # XGBoost approval model (model_xgboost.json)
        xgb_path = os.path.join(models_dir, "model_xgboost.json")
        if os.path.exists(xgb_path):
            try:
                from xgboost import XGBClassifier
                xgb_model = XGBClassifier(objective="binary:logistic")
                
                try:
                    xgb_model._estimator_type = "classifier"
                    xgb_model.load_model(xgb_path)
                    if not hasattr(xgb_model, "n_classes_") or xgb_model.n_classes_ is None:
                        xgb_model.n_classes_ = 2
                    if not hasattr(xgb_model, "classes_") or xgb_model.classes_ is None:
                        xgb_model.classes_ = np.array([0, 1])
                except Exception as e:
                    api_logger.warning(f"Standard XGB load failed, using booster fallback: {e}")
                    import xgboost as xgb
                    bst = xgb.Booster()
                    bst.load_model(xgb_path)
                    xgb_model._Booster = bst
                    xgb_model._estimator_type = "classifier"
                    xgb_model.n_classes_ = 2
                    xgb_model.classes_ = np.array([0, 1])
                    
                models["approval"] = xgb_model
                api_logger.info(f"Loaded approval XGBoost model ✓")
            except Exception as e:
                api_logger.error(f"Critical failure loading approval model: {e}")
        else:
            api_logger.warning(f"Approval model not found at {xgb_path}")

        # Occupation encoder (encoder_occupation.joblib)
        models["occ_encoder"] = _load_joblib(
            os.path.join(models_dir, "encoder_occupation.joblib"), "occupation encoder"
        )

    # For now, we still load on startup but in a more controlled way.
    # True lazy loading would move this inside the request handlers.
    load_all_models()


    # Threshold JSON
    models["threshold"] = 0.5
    for tp in [os.path.join(models_dir, "threshold.json"),
               os.path.join(models_dir, "..", "threshold.json")]:
        if os.path.exists(tp):
            try:
                import json
                with open(tp) as f:
                    models["threshold"] = json.load(f).get("best_threshold", 0.5)
                api_logger.info(f"Loaded threshold: {models['threshold']} ({tp})")
                break
            except Exception as e:
                api_logger.warning(f"Could not load threshold.json: {e}")

    # Initialize Chroma knowledge base for RAG (auto-load all 1000+ documents on startup)
    models["chroma_initialized"] = False
    try:
        from rag.ingest import ingest_migration_documents
        from rag.chroma_client import get_or_create_collection
        import asyncio
        import signal
        
        async def init_chroma_with_timeout():
            import asyncio
            try:
                # Check if ChromaDB already has documents - if yes, skip ingestion (fast startup)
                collection = get_or_create_collection()
                doc_count = collection.count()
                
                if doc_count > 0:
                    api_logger.info(f"✅ Chroma knowledge base already initialized with {doc_count} documents (skipping re-ingestion)")
                    models["chroma_initialized"] = True
                    return True
                
                # First ingestion only: use 30-minute timeout for 4200+ documents (fast with local embeddings)
                api_logger.info("🚀 First-time ingestion: loading 4200+ documents with local embeddings (this will take ~2-3 minutes)...")
                await asyncio.wait_for(asyncio.to_thread(ingest_migration_documents), timeout=1800.0)  # 30 minutes
                models["chroma_initialized"] = True
                api_logger.info("✅ Chroma knowledge base fully initialized with 4200+ documents")
                return True
            except asyncio.TimeoutError:
                api_logger.warning("⚠️  Chroma initialization timed out after 30 min—continuing with basic RAG")
                models["chroma_initialized"] = False
                return False
            except Exception as e:
                api_logger.warning(f"⚠️  Chroma initialization error: {e}—continuing with basic RAG")
                models["chroma_initialized"] = False
                return False
        
        try:
            # Run in background so server startup doesn't block
            asyncio.create_task(init_chroma_with_timeout())
        except Exception as e:
            api_logger.warning(f"Could not initialize Chroma: {e}")
            
    except Exception as e:
        api_logger.warning(f"Chroma import/setup error: {e}")
        models["chroma_initialized"] = False

    # Initialize SQL database tables (conversation history, etc.)
    try:
        api_logger.info("Initializing database tables...")
        await init_db()
        
        # Ensure at least one superadmin exists
        from services.admin_init import ensure_superadmin
        ensure_superadmin()
        
        api_logger.info("✅ Database initialized successfully")
    except Exception as e:
        api_logger.error(f"❌ Failed to initialize database: {e}")
    
    # Initialize scheduler for background tasks (activity log cleanup)
    try:
        from scheduler import start_scheduler, stop_scheduler
        scheduler = start_scheduler()
        models["scheduler"] = scheduler
    except Exception as e:
        api_logger.warning(f"⚠️  Scheduler initialization error: {e}")
        models["scheduler"] = None
    
    api_logger.info("Interlace API started")
    yield

    
    # Shutdown scheduler
    if models.get("scheduler"):
        try:
            from scheduler import stop_scheduler
            stop_scheduler(models["scheduler"])
        except Exception as e:
            api_logger.warning(f"Error stopping scheduler: {e}")
    
    models.clear()
    api_logger.info("Shutdown — models cleared")


app = FastAPI(
    title="Interlace Migration Intelligence API",
    version="1.0.0",
    lifespan=lifespan,
)

# Global exception handler to prevent generic 500 "Internal Server Error"
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    api_logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "message": str(exc)}
    )

import asyncio
import httpx

async def prewarm_cache():
    """
    Optimized pre-warming: Calls internal router logic directly 
    instead of making external HTTP requests to itself.
    """
    await asyncio.sleep(5)  # Let server settle
    api_logger.info("🔥 Starting background cache pre-warm...")
    
    from db.database import AsyncSessionLocal
    from routers.data import get_summary, get_quota, get_eoi_monthly, get_eoi_occupations
    
    async with AsyncSessionLocal() as db:
        try:
            # Pre-warm key endpoints
            await get_summary(db)
            await get_quota(db)
            await get_eoi_monthly(db)
            await get_eoi_occupations(page=1, db=db)
            api_logger.info("✅ Core data cache pre-warmed.")
        except Exception as e:
            api_logger.warning(f"⚠️  Background pre-warm failed: {e}")

@app.on_event("startup")
async def startup_prewarm():
    asyncio.create_task(prewarm_cache())

# Rate limiting middleware
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from fastapi.responses import JSONResponse

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(
        status_code=429,
        content={"detail": "Too many requests"}
    ))
except ImportError:
    print("⚠️  slowapi not installed - rate limiting disabled")
    limiter = None

allowed_origins_env = os.environ.get("ALLOWED_ORIGINS")
if allowed_origins_env:
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
else:
    allowed_origins = [
        "http://localhost:3000", 
        "http://127.0.0.1:3000", 
        "https://*.vercel.app", 
        "https://migration-dashboard.interlacestudies.com"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import data, predict, llm, reports, search, report_generator, conversation, auth, admin
app.include_router(data.router,            prefix="/api/data",    tags=["Data"])
app.include_router(predict.router,         prefix="/api/predict", tags=["Predict"])
app.include_router(llm.router,             prefix="/api/llm",     tags=["LLM"])
app.include_router(reports.router,         prefix="/api/reports", tags=["Reports"])
app.include_router(search.router,          tags=["Search"])
app.include_router(report_generator.router, tags=["Report Generator"])
app.include_router(conversation.router,    prefix="/api/conversation", tags=["Conversation"])
app.include_router(auth.router,            tags=["Authentication"])
app.include_router(admin.router,           tags=["Admin"])


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "database": "connected",
        "models_loaded": {k: (v is not None) for k, v in models.items()},
        "keys": list(models.keys()),
    }
