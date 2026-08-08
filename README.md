# 🏗️ System Architecture Documentation

> Full-stack ML prediction platform with RAG-powered chat, built on React (Next.js App Router) + FastAPIddddddddddddddddddddddddddddd

---

## 📐 Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                   FRONTEND — Next.js (App Router)           │
│    Dashboard  │  Predictors  │  Chat  │  Reports  │  Admin  │
└────────────────────────────┬────────────────────────────────┘
                             │
                   REST API + SSE Streaming
                             │
┌────────────────────────────▼────────────────────────────────┐
│                   BACKEND — FastAPI (Railway)               │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │ /api/data/* │   │/api/predict/*│   │   /api/llm/*     │  │
│  │ 6 endpoints │   │ 3 ML models  │   │ Claude streaming │  │
│  │ Redis cached│   │ SHAP explain │   │   Mock RAG search│  │
│  └─────────────┘   └──────────────┘   └──────────────────┘  │
└──────┬───────────────────┬────────────────────┬─────────────┘
       │                   │                    │
┌──────▼──────┐   ┌────────▼───────┐   ┌────────▼──────────┐
│  SQLite /   │   │  ML Models     │   │ Mock RAG / ChromaDB│
│  PostgreSQL │   │  (.joblib/.json)│  │                    │
│             │   │                │   │ Vector store (Plan)│
│ 6 tables    │   │ 3 serialised   │   │ RAG + job queue    │
│ migration   │   │ loaded at      │   │ (Mock for now)     │
│ warehouse   │   │ startup        │   │                    │
└─────────────┘   └────────────────┘   └────────────────────┘
```

---

## 🗂️ Project Structure

```text
project/
├── frontend/                   # React App (Next.js 14)
│   ├── src/
│   │   ├── app/
│   │   │   ├── dashboard/      # Core dashboard layouts & pages
│   │   │   │   ├── pathway/
│   │   │   │   ├── reports/
│   │   │   │   └── ...
│   │   │   ├── api/            # Next.js API Routes (if any)
│   │   │   ├── login/          # Auth pages
│   │   │   ├── layout.tsx      # Root layout
│   │   │   └── globals.css     # Tailwind styles
│   │   ├── components/         # Reusable UI components
│   │   │   ├── ui/             # Radix-ui / Base primitives
│   │   │   └── shared/         # Custom shared library (Skeleton, ScoreBadge, PredictorCard, FormLabel)
│   │   └── hooks/
│   │       └── useSSE.js       # Server-Sent Events hook
│   ├── tailwind.config.js      # CSS Framework configuration
│   └── package.json            # Scripts & dependencies (Zustand, SWR, Next-Auth)
│
├── backend/                    # FastAPI App
│   ├── main.py
│   ├── routers/
│   │   ├── data.py             # /api/data/*
│   │   ├── predict.py          # /api/predict/*
│   │   ├── llm.py              # /api/llm/*
│   │   └── reports.py          # /api/reports/*
│   ├── models/                 # ML Models
│   │   ├── model_a.joblib           # GBM Pathway pipeline
│   │   ├── model_xgboost.json       # XGBoost Approval Model
│   │   └── encoder_occupation.joblib# label encoder
│   ├── db/
│   │   ├── database.py         # SQLAlchemy setup
│   │   ├── models.py           # 6 ORM Models (eoi_records, osl_shortage, etc)
│   │   └── schema.sql
│   ├── rag/
│   │   └── __init__.py         # Placeholder for future ChromaDB integration
│   ├── cache/
│   │   └── redis_client.py
│   └── requirements.txt
│
└── README.md
```

---

## 🔄 Workflow Breakdown

---

### 1️⃣ Dashboard Workflow

**Purpose:** Display aggregated data metrics and KPIs.

```text
User visits /dashboard
        │
        ▼
React fetches GET /api/data/summary
        │
        ▼
FastAPI checks Redis cache
    ├── HIT  → return cached JSON immediately
    └── MISS → query PostgreSQL/SQLite
                    │
                    ▼
              cache result in Redis (TTL: e.g. 5 min)
                    │
                    ▼
        return JSON to React
                    │
                    ▼
        React renders charts/tables
```

**Key files:**

- Frontend: `src/app/dashboard/page.tsx`
- Backend: `routers/data.py` → `GET /api/data/summary`
- Cache: Redis with TTL

---

### 2️⃣ Predictors Workflow

**Purpose:** Run ML model inference with explainability via SHAP.

```text
User fills prediction form
        │
        ▼
React sends POST /api/predict/{model_name}
  body: { feature_1, feature_2, ... }
        │
        ▼
FastAPI router loads pre-loaded model memory obj
  (models loaded into memory at startup — no disk I/O per request)
        │
        ▼
Run model.predict(input_data) / model.predict_proba(input_data)
        │
        ▼
Run SHAP explainer → feature importance values (for pathway GBM)
        │
        ▼
Return JSON:
  {
    "prediction": 0.87,
    "confidence": 0.92,
    "shap_values": { "feature_1": 0.32, ... }
  }
        │
        ▼
React renders prediction result + SHAP bar chart
```

**Key files:**

- Frontend: `src/app/dashboard/pathway/page.tsx` (Pathway predictor)
- Backend: `routers/predict.py` → `POST /api/predict/{model}`
- Models: `models/model_a.joblib` (3-feature GBM), `models/model_xgboost.json` (XGBoost 2.0)

---

### 3️⃣ Chat Workflow (RAG + Claude Streaming)

**Purpose:** AI-powered chat with contextual document search using RAG.

```text
User types a message → clicks Send
        │
        ▼
React sends POST /api/llm/chat
  body: { message: "...", session_id: "..." }
        │
        ▼
FastAPI RAG pipeline:
  1. Retrieve mock documents (Currently placeholder for ChromaDB search)
  2. Build prompt: system + retrieved context + user message
        │
        ▼
FastAPI calls Anthropic Claude API (streaming via AsyncAnthropic)
        │
        ▼
FastAPI returns SSE stream (text/event-stream):
  data: {"token": "Hello"}
  data: {"token": " there"}
  data: [DONE]
        │
        ▼
React useSSE() hook reads stream token by token
        │
        ▼
UI renders text progressively as it arrives
```

**Key files:**

- Frontend: `hooks/useSSE.js`
- Backend: `routers/llm.py` → `POST /api/llm/chat`
- RAG: Temporary mock retrieval (awaiting full implementation in Sprint 5).

---

### 4️⃣ Reports Workflow

**Purpose:** Generate and download data reports in PDF format.

```text
User profiles input & selects parameters → clicks Generate PDF
        │
        ▼
React calls GET /api/reports/generate (with URL params)
        │
        ▼
FastAPI queries models natively, fetching probabilities and shortage/quota features
        │
        ▼
FastAPI outputs structured JSON payload
        │
        ▼
Triggers Puppeteer (Node.js script `generate_report.js`) using JSON payload
        │
        ▼
Generates PDF and sends via `FileResponse` to user
```

**Key files:**

- Frontend: `src/app/dashboard/reports/page.tsx`
- Backend: `routers/reports.py` → `GET /api/reports/generate`
- Generator: `generate_report.js` (Node-based Puppeteer PDF generator)

---

### 5️⃣ Admin Workflow

**Purpose:** Manage users, data, models, and system config.

```text
Admin navigates to /admin
        │
        ▼
React fetches GET /api/data/admin/* (auth-protected via Next-Auth and FastAPI JWT rules)
        │
        ▼
FastAPI validates authorization
    ├── FAIL → 401 Unauthorized
    └── PASS → process request
                    │
                    ▼
             CRUD on DB tables
             OR trigger model retraining workflows
                    │
                    ▼
             return result to React
```

**Key files:**

- Frontend: `src/app/dashboard/admin/page.tsx`
- Backend: `routers/data.py` (admin sub-routes), auth middleware

---

## 🗄️ Database Layer

### SQLite / PostgreSQL

| Detail     | Value                                                                                                                                  |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Tables     | 6 main data tables (`eoi_records`, `osl_shortage`, `employment_projections`, `migration_grants`, `visa_grants`, `occupation_features`) |
| ORM        | SQLAlchemy                                                                                                                             |
| Migrations | Alembic / Auto-schema generation                                                                                                       |
| Dev        | SQLite (local `warehouse.db`)                                                                                                          |
| Prod       | PostgreSQL (Railway)                                                                                                                   |

---

## 🤖 ML Models Layer

| Detail         | Value                                                                                         |
| -------------- | --------------------------------------------------------------------------------------------- |
| Formats        | `.joblib` & `.json` serialised models                                                         |
| Pathway Model  | Gradient Boosting (3 features: `occupation`, `state`, `points`) - Trained on 32k real records |
| Approval Model | XGBoost 2.0 (13 features) - Manual metadata injection for compatibility                       |
| Explainability | SHAP values for Pathway GBM + Dynamic Feature Importance for XGBoost                          |

**Startup loading pattern:**

```python
# main.py startup logic
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load scikit-learn GBM (Model A)
    models["pathway"] = joblib.load("models/model_a.joblib")

    # Load XGBoost (Model B) with Manual Metadata Fix
    # Injects n_classes_ and _estimator_type for XGBoost 2.0+ stability
    xgb = XGBClassifier()
    xgb.load_model("models/model_xgboost.json")
    xgb.n_classes_ = 2
    xgb._estimator_type = "classifier"
    models["approval"] = xgb

    models["occ_encoder"] = joblib.load("models/encoder_occupation.joblib")
    yield
    models.clear()

app = FastAPI(lifespan=lifespan)
```

---

## 🧠 ChromaDB + Redis Layer

| Component | Purpose                                                                                         |
| --------- | ----------------------------------------------------------------------------------------------- |
| ChromaDB  | Vector store for RAG document embeddings (Pending Sprint 5 implementation, currently mock data) |
| Redis     | HTTP response cache + background job queue (Railway add-on)                                     |

**RAG flow:**

1. Future capability: User query -> chunk embed -> similarity search using ChromaDB.
2. Currently using hardcoded retrieval strings in backend API to simulate search.
3. Chunks injected into Claude prompt as context.

---

## 🚀 Deployment

| Layer       | Platform                                         |
| ----------- | ------------------------------------------------ |
| Frontend    | Vercel (Next.js App Deployment)                  |
| Backend     | Railway (FastAPI + Uvicorn)                      |
| Database    | Railway PostgreSQL add-on                        |
| Cache/Queue | Railway Redis add-on                             |
| Vector DB   | Planned as ChromaDB Persistent Volume on Railway |

---

## ⚙️ Environment Variables

```env
# Backend (.env)
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://localhost:6379
ANTHROPIC_API_KEY=sk-ant-...
CHROMA_PERSIST_DIR=./chroma_db

# Frontend (.env.local)
NEXT_PUBLIC_API_BASE_URL=https://your-backend.railway.app
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=secret
```

---

## 🛠️ Tech Stack Summary

| Layer     | Technology                                                                |
| --------- | ------------------------------------------------------------------------- |
| Frontend  | Next.js 14, React 18, Tailwind CSS, Recharts, Custom **Skeleton Loaders** |
| Backend   | FastAPI, Python 3.10+, SQLite (Optimized Shared Connection)               |
| ML Models | **GBM (3-feature schema)**, XGBoost 2.0.3, SHAP Explainer                 |
| UI Assets | Shared components: `ScoreBadge`, `PredictorCard`, `FormLabel`, `Skeleton` |
| PDF Gen   | Puppeteer (Node.js integrated reporting)                                  |

---

## 🚀 Getting Started

### Initial Backend Setup

Before running the backend server, ensure the dependencies are installed and the initial models are trained:

1. **Install Dependencies**

   install the required packages:

   ```bash
   #windows
   winget install Python.Python.3.x
   #linux
   sudo 'package-manager' install python3
   #mac
   brew install python3
   ```

   it's recommended to use virtual environment

   ```bash
   py -m venv venv
   venv/Scripts/activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

   for frontend:

   ```bash
   cd frontend
   npm install
   ```

2. **Import Datasets**

   first you got to import datasets into folder named `data/raw/` in `backend/` directory

   and run the main ingestors script from `backend/pipelines/ingestors/`:

   ```bash
   cd backend
   python pipelines/ingestors/ingestors.py
   ```

   or run each ingestor individually:

   ```bash
   cd backend
   python pipelines/ingestors/eoi_ingestor.py
   python pipelines/ingestors/osl_ingestor.py
   python pipelines/ingestors/quota_ingestor.py
   python pipelines/ingestors/jsa_ingestor.py
   python pipelines/ingestors/nero_ingestor.py
   ```

3. **Train the ML Models**

   Generate the initial `.joblib` model by running the training script:

   ```bash
   cd backend
   python train.py
   ```

4. **Setup ENV**

   copy .env.example to .env and move it to backend folder

### Running the Application

**Backend Server (FastAPI)**

```bash
cd backend
uvicorn main:app --reload
```

_The API will be accessible at http://localhost:8000._

**Frontend Server (Next.js)**

```bash
cd frontend
npm run dev
```

_The web interface will be accessible at http://localhost:3000/dashboard._
