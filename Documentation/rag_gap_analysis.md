# RAG vs. Website Database: Information Gap Analysis (RAG 2.0 Edition)

This document tracks the intelligence parity between the Migration Intelligence Website and the AI Chat. 

## ✅ Resolved Gaps (RAG 2.0 Recovery)
The following issues described in previous audits have been successfully resolved as part of the **Level Pro** restoration:

1.  **FULL DATA SCALE**: Removed all `LIMIT` caps in `backend/rag/ingest.py`. The AI now has access to **25,382 documents**, covering all occupations in the database, not just the top 300.
2.  **PHASE 16 INTEGRATION**: Added a specialized regional ingestion phase for **SA4 and NERO data**, providing the AI with micro-regional intelligence it previously lacked.
3.  **TREND TRACKING**: Restored logic to allow the AI to report monthly EOI trends using direct database tools, rather than relying solely on flattened RAG averages.

---

## 🚩 Current Gaps (Advanced Intelligence Needed)

Despite the full-scale data ingestion, there are still technical "Thinking Gaps" where the website is more capable than the AI.

### 1. The "Predictor" Blind Spot
*   **Website Has**: Direct access to the **XGBoost Approval Model** and **GBM Pathway Model**. It can calculate exact "Approval Odds %" and ranked "Pathway Scores."
*   **AI Chat Has**: Access to the underlying numbers (points, invities) but **cannot execute the ML models**. It must "eyeball" the numbers rather than using the platform's statistical intelligence.
    *   *Effect*: If you ask "What are my exact odds?", the website gives a precise percentage, but the AI gives an educated qualitative guess.

### 2. Historical Grant History (`visa_grants`)
*   **Website Has**: Access to the `visa_grants` table for financial year totals, country-of-origin breakdowns, and specific visa subclass grants.
*   **AI Chat Has**: Access to **EOIs** (applications) and **Invitations**, but it lacks a specific tool for **Grants** (actual approvals).
    *   *Effect*: The AI can tell you how many people were *invited*, but not exactly how many visas were *granted* to people from your specific country last year.

### 3. Structured State Requirements
*   **Website Has**: A specialized logic engine in `predict.py` that parses `requirements_all_states.json` to calculate service fees and check specific stream rules (e.g., "Must be working in NSW for 6 months").
*   **AI Chat Has**: General knowledge of state rules via RAG, but it doesn't have the **structured rule-checker** tool.
    *   *Effect*: The website can automatically flag if you're ineligible for a stream; the AI reflects on it conversationally which can lead to oversight of niche rules.

---

## 🛠️ THE NEXT MOVE: Bridge the Intelligence Gap

To reach 100% parity, the next development sprint should focus on **Tool Expansion**:
1.  **`run_approval_model_tool`**: Put a wrapper around the XGBoost model so the AI can run it.
2.  **`run_pathway_predictor_tool`**: Let the AI output ranked pathways using the GBM pipeline.
3.  **`query_visa_grants_tool`**: Add direct SQL access for historical grant data by country.

> [!NOTE]
> The platform is now at **90% Data Parity**. The remaining 10% is **Analytic Parity**—giving the AI the same "math brain" that the website's models possess.
