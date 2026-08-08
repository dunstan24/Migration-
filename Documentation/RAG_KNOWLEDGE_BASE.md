# RAG (Retrieval Augmented Generation) — Intelligence Guide

This guide covers the architecture, data depth, and setup instructions for the Migration Intelligence Platform's RAG system.

## 📊 Current Scale: 16 Phases (~25,382 Documents)

The system is now powered by **RAG 2.0**, a high-density knowledge base synced from 20+ database tables. It provides deep qualitative context that supplements raw SQL statistics.

---

## 🛠️ First-Time Setup & Ingestion

The RAG system requires a "First-Time Ingestion" to populate the ChromaDB vector store. This process takes approximately **2-5 minutes** depending on your hardware.

### Option A: Auto-Setup (Recommended)
1.  **Start the Backend**:
    ```bash
    cd backend
    python -m uvicorn main:app --host 0.0.0.0 --port 8000
    ```
2.  **Wait for Lifespan Trigger**: The system automatically detects if the `migration-docs` collection is empty.
3.  **Monitor Logs**: You will see `🚀 First-time ingestion: loading 25k+ documents...` followed by `✅ Success!`.

### Option B: Manual Ingest (Hot Reload)
If you update the source data and want to force a refresh:
1.  **POST Request**: Send an empty POST request to:
    `http://localhost:8000/api/llm/ingest`
2.  **Verify**: Check the terminal logs for the Phase 1 through Phase 16 progress indicators.

---

## 🏗️ Deep Data Architecture (16 Phases)

The knowledge base is built through a surgical 16-phase process:

1.  **⚖️ Phase 1 (Core Policy)**: Federal migration strategies, visa subclass rules (189, 190, 491).
2.  **💼 Phase 2 (Occupations)**: Full EOI profiles for all 1,000+ ANZSCO codes.
3.  **⚠️ Phase 3 (Shortage)**: OSL and JSA state-by-state shortage ratings.
4.  **📊 Phase 4 (Employment)**: National vacancy rates and employment totals.
5.  **🎓 Phase 5 (Education)**: Degree requirements and field-of-study matching.
6.  **🏛️ Phase 6 (Quotas)**: Annual planning levels and state-specific allocation caps.
7.  **👥 Phase 7 (Demographics)**: Age/Gender profiles of the current workforce.
8.  **📢 Phase 8 (Job Ads)**: Monthly Internet Vacancy Index (IVI) data.
9.  **⭐ Phase 9 (Top Occs)**: "Fastest Growth" and "Highest Demand" rankings.
10. **🤝 Phase 10 (Recruitment)**: Average applicants per job and experience requirements.
11. **📈 Phase 11 (JSA Shortage)**: Multi-year shortage history from Jobs and Skills Australia.
12. **📡 Phase 12 (Projections)**: 5-year and 10-year employment growth forecasts.
13. **🔄 Phase 13 (Mobility)**: Data on career transitions (e.g., Accountant to General Manager).
14. **🔮 Phase 14 (Forecasts)**: Probabilistic shortage outcomes through 2028.
15. **📍 Phase 15 (NERO Index)**: Regional employment strength and remoteness data.
16. **🗺️ Phase 16 (SA4 Regional)**: Localized insights for specific suburbs and regional hubs.

---

## 🛡️ Self-Correction & Reliability
The RAG system is integrated with the **Level Pro AI Router**:
*   **Thresholding**: Every retrieved document must meet a `0.75` relevance score or it is discarded.
*   **Verification**: The AI is instructed to cross-verify RAG insights against direct SQL counts using the provided tools.
*   **Provenance**: Every answer generated from RAG is prefixed by the AI to distinguish it from exact database counts.

> [!IMPORTANT]
> Ensure your `.env` contains a valid `GEMINI_API_KEY`. While embeddings are generated locally (`all-MiniLM-L6-v2`), the final reasoning and tool execution require the Gemini API.

> [!TIP]
> If you encounter `ECONNREFUSED` on the dashboard, it usually means the backend is still in the middle of a first-time ingestion. Wait for the `✅ Success!` log before querying.
