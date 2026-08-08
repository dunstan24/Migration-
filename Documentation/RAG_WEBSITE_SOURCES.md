# RAG Website Information Sources

## Overview

Your RAG system gets website page information from **Phase 17** of the document ingestion pipeline.

---

## 📍 Where Website Information Is Retrieved

### Source File Location

**File:** `backend/data/website_context.txt`

The RAG system is configured to load website context data from this single text file during ingestion. The file is split into blocks (separated by double newlines `\n\n`) and each block is treated as one document.

### Ingestion Process

1. **File Path:** `backend/data/website_context.txt`
2. **When Loaded:** During FastAPI startup or when `/api/llm/ingest` endpoint is called (manual ingestion)
3. **Storage:** Documents are stored in ChromaDB vector database under the `migration-docs` collection
4. **Document ID Pattern:** `phase17_website_[topic_title]`
5. **Metadata:** Each website document is tagged with:
   - `category`: `website_knowledge`
   - `title`: Extracted from the text block
   - `source`: `website_context.txt`

---

## 🔍 How RAG Retrieves Website Information

### Query Process

When a user asks a question in the chat:

1. **Query Received** → `/api/llm/chat` endpoint (in `backend/routers/llm.py`)
2. **Knowledge Base Search** → Uses `search_knowledge_base()` function from `backend/rag/tools.py`
3. **Vector Search** → Searches ChromaDB with relevance scoring
4. **Document Retrieval** → Returns up to 5 most relevant documents with similarity scores
5. **Filtering** → Only documents with distance < 0.8 are considered relevant
6. **Response Generation** → Gemini AI uses these documents as context

### RAG Integration Points

**In `backend/routers/llm.py`:**

```python
from rag.tools import search_knowledge_base
# Used during chat message processing to supplement AI responses
```

**In `backend/rag/tools.py`:**

- `search_knowledge_base(query: str)` - Main function that searches migration-docs collection
- Returns formatted results with document snippets

---

## 📊 Complete RAG Data Architecture (17 Phases)

| Phase  | Source                                                  | Type             | Purpose                            |
| ------ | ------------------------------------------------------- | ---------------- | ---------------------------------- |
| 1      | Hardcoded                                               | Policy docs      | Core visa rules, points system     |
| 2      | `eoi_records` table                                     | Occupations      | 1,000+ occupation profiles         |
| 3      | `osl_shortage` table                                    | Shortage data    | State-by-state shortages           |
| 4      | `employment_data` table                                 | Employment       | Vacancy rates, national employment |
| 5      | `jsa_education` table                                   | Education        | Degree requirements per occupation |
| 6      | `state_nomination_quotas` & `national_migration_quotas` | Quotas           | Migration allocations by state     |
| 7      | `demographics` table                                    | Demographics     | Age/gender workforce profiles      |
| 8      | `monthly_job_ads` table                                 | Job Ads          | Internet Vacancy Index data        |
| 9      | `jsa_top10` table                                       | Top Occupations  | High-demand rankings               |
| 10     | `jsa_recruitment` table                                 | Recruitment      | Placement rates, applicant counts  |
| 11     | `jsa_shortage` table                                    | JSA Shortage     | Multi-year shortage history        |
| 12     | `employment_projection` table                           | Projections      | 5-10 year employment forecasts     |
| 13     | `mobility_data` table                                   | Career Mobility  | Transition paths between roles     |
| 14     | `migration_volume_forecast` & `shortage_forecast`       | Forecasts        | Probabilistic outcomes 2026-2028   |
| 15     | `nero_northern` & `nero_regional` tables                | NERO Index       | Regional employment strength       |
| 16     | `nero_sa4` table                                        | SA4 Regional     | Suburb/micro-region insights       |
| **17** | **`website_context.txt`**                               | **Website Info** | **Custom website page content**    |

---

## 💾 Database Tables Used for RAG

The RAG system pulls from these SQLite tables in `backend/data/processed/warehouse.db`:

1. **eoi_records** - EOI applications with occupation, status, points
2. **osl_shortage** - Occupation shortage by state
3. **employment_data** - National vacancy and employment totals
4. **jsa_education** - Education field requirements per ANZSCO
5. **state_nomination_quotas** - State-specific visa quotas
6. **national_migration_quotas** - National-level allocations
7. **demographics** - Workforce age/gender distribution
8. **monthly_job_ads** - Internet Vacancy Index
9. **jsa_top10** - High-demand occupation rankings
10. **jsa_recruitment** - Placement and applicant statistics
11. **jsa_shortage** - JSA shortage ratings
12. **employment_projection** - 5-10 year employment growth
13. **mobility_data** - Career transition information
14. **migration_volume_forecast** - Volume forecasts
15. **shortage_forecast** - Probabilistic shortage forecasts
16. **nero_northern** - Northern Australia NERO index
17. **nero_regional** - Regional Australia NERO index
18. **nero_sa4** - SA4 region employment data

---

## ⚙️ How to Add Website Information

### Current Status

The `website_context.txt` file **does not currently exist**. To enable Phase 17, you need to:

### Step 1: Create the File

```bash
mkdir -p backend/data
```

### Step 2: Add Website Content

Create `backend/data/website_context.txt`:

```
What is This Platform?: This is the Migration Intelligence Platform, designed to help Australian migration professionals analyze visa trends and occupational insights.

How to Use the Chat?: Ask questions about occupations, visa types, shortage rates, employment data, and migration pathways. The system uses both live database data and historical trend analysis.

Occupations We Track: We monitor 1000+ ANZSCO occupations including healthcare, engineering, IT, construction, and education roles.

Database Statistics: Our system analyzes 25,000+ vector documents covering national migration data, state-specific information, and regional employment insights.

Visa Types Supported: We provide guidance on Visa 189 (Skilled Independent), Visa 190 (Skilled Nominated), and Visa 491 (Skilled Regional).
```

Each block separated by a blank line becomes one document.

### Step 3: Trigger Ingestion

```bash
# Option 1: Restart the backend (Phase 17 runs automatically)
python -m uvicorn main:app --reload

# Option 2: Manual ingestion via API
curl -X POST http://localhost:8000/api/llm/ingest
```

---

## 🔗 Code References

### Ingestion

- **File:** `backend/rag/ingest.py` (lines 781-814)
- **Function:** `load_website_context()`
- **Collection:** `migration-docs`

### Retrieval

- **File:** `backend/rag/tools.py` (lines 57-72)
- **Function:** `search_knowledge_base(query: str)`

### Chat Integration

- **File:** `backend/routers/llm.py`
- **Endpoint:** `POST /api/llm/chat`
- **Stream Processing:** Uses Gemini AI with RAG context

---

## 📈 Relevance Scoring

The RAG system filters documents based on vector similarity:

- **Relevance Threshold:** 0.75 (configurable)
- **Distance Metric:** Cosine similarity
- **Embedding Model:** `all-MiniLM-L6-v2` (384-dimensional, local)
- **Max Results:** 5 documents per query
- **Filter Rule:** Only documents with distance < 0.8 are included

Website documents are scored the same way as database documents, so they must semantically match the user's query to be retrieved.

---

## ✅ Verification

To verify that Phase 17 is working:

1. Check backend logs for: `🌐 Phase 17: Website Context - Loaded X website knowledge blocks`
2. Query the chat with a question related to website content
3. Check if responses reference website information in the knowledge base results
4. Use ChromaDB tools to inspect the `migration-docs` collection for documents with `source: website_context.txt`

---

## 📝 Additional Notes

- Website information is **optional** - the system works without it
- If `website_context.txt` is missing, Phase 17 simply **skips** with a warning
- Website documents are treated like all other RAG documents - subject to semantic matching
- The system does **NOT** automatically crawl websites - all website info must be manually provided in the text file
