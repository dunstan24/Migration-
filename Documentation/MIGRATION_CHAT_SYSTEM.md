# Migration Intelligence Platform: Advisor Chat Documentation

This document provides a comprehensive overview of the **Migration Advisor Chat** system, its features, underlying logic, and the depth of data available within its RAG (Retrieval-Augmented Generation) framework.

## 1. Overview
The Migration Advisor Chat is a high-intelligence, data-verified conversational assistant designed to provide accurate, real-time insights into the Australian migration landscape. Unlike generic AI, it is hard-wired into the platform's **Migration Warehouse** and uses a multi-stage reasoning pipeline to prevent hallucinations.

---

## 2. Key Features

### 🛡️ Level Pro Self-Correction
The chat features an advanced self-correction loop that acts as a quality gate for all AI responses:
- **Typo Protection (Typofuzz)**: Every occupation mentioned by the user is automatically cross-referenced against a verified list of 1,000+ ANZSCO occupations using fuzzy matching (rapidfuzz).
- **Suspicion Detection**: The system monitors tool outputs for "suspicious" results (e.g., missing data, zero invitations, or logical inconsistencies).
- **The 3-Step Retry Loop**: If a query yields suspicious results, the AI automatically retries using alternative search strategies (Strict Match -> Fuzzy Match -> Broad RAG Search) before presenting the answer.

### 📊 Data Transparency & Traceability
The system is designed for high-stakes decision-making. Every data point provided in the chat is explicitly tagged with its source:
- "Database Result: ..." (Direct SQL query from `warehouse.db`)
- "Knowledge Base Insight: ..." (Contextual retrieval from `ChromaDB`)

### ⚡ Real-Time Streaming (SSE)
The chat uses **Server-Sent Events (SSE)** to stream tokens instantly as they are generated. 
- **Manual Decoding**: The frontend uses a custom-built decoding loop to handle incoming data chunks, ensuring stability even under heavy network load or long-form reasoning.
- **Pulse Indicators**: The UI features a real-time "thinking" cursor and status dots that change color based on the system's state (Streaming, Ready, or Busy).

---

## 3. How It Works: The Reasoning Pipeline

1.  **Intent Classification**: The system determines if the user is asking for exact statistics (counts, points), trends, state-specific data, or general advice.
2.  **Tool Orchestration**:
    *   **SQL Tools**: Query the structured **Migration Warehouse** for precise EOI counts, invitation stats, and monthly trends.
    *   **RAG Search**: Queries the vectorized **Knowledge Base** for qualitative data, policy nuances, and regional insights.
3.  **Cross-Verification**: The Gemini 2.5 engine compares raw data against its training set to ensure the findings are logical within the context of Australian migration.
4.  **Final Synthesis**: The answer is formatted with clear headings, pill-styled badges, and direct citations.

---

## 4. The RAG Knowledge Base (25,000+ Documents)

The chat's "Intelligence" comes from 16 distinct phases of data ingestion, providing depth that manual databases cannot match:

| Phase | Content Area | Data Sources |
| :--- | :--- | :--- |
| **1-2** | Policy & Occupations | Migration Strategy 2024, Skilled Occupation Lists |
| **3-4** | Employment & Shortage | JSA Labour Market Atlas, National Skills Commission |
| **5-7** | Education & Demographics | Higher Ed placements, Age/Location demographics |
| **8-9** | Job Ads & Rankings | Monthly Internet Vacancy Index (IVI), Top 10 Occupations |
| **10-12** | Recruitment & Prospects | JSA Recruitment surveys, 5-year Job Projections |
| **13-14** | Mobility & Forecasts | Career transition data, AI-modeled volume forecasts |
| **15-16** | Regional Intelligence | NERO Regional index, SA4 Localized Insights |

---

## 5. Dashboard Integration

The chat page is integrated directly into the **Monitoring Dashboard**, providing the user with real-time feedback on system health:
- **System Intelligence Panel**: Shows the status of Self-Correction and Typo Protection.
- **Knowledge Base Panel**: Live counters showing the total EOI records (8.3M+) and document ingestion status (Phase 1-16 Synced).
- **Active Session Management**: Transparent session IDs allow for conversational memory and history retrieval.

---

## 6. Technical Stack
- **Backend**: FastAPI, SQLAlchemy (Sync/Async), SQLite, ChromaDB.
- **LLM**: Google Gemini 2.5 (Flash/Pro) with fallback resilience.
- **Frontend**: Next.js 14, React Hooks (`useConversation`, `useSSE`), Vanilla CSS Modules.
- **Fuzzy Search**: `rapidfuzz` for high-speed occupation correction.
