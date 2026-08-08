# RAG Data Structure - RAG 2.0 Overview

## CHROMADB VECTOR DATABASE STRUCTURE

```
migration-docs (Collection)
│
├─── PHASE 1: Core Policy (8 docs)
│    ├─ visa_189
│    ├─ visa_190_vs_491_differences
│    ├─ points_system
│    └─ visa_processing
│
├─── PHASE 2: Occupations (1,000+ docs)
│    ├─ Detailed EOI profiles (Total Apps, Avg Points)
│    └─ Cross-referenced with warehouse.db
│
├─── PHASE 3: Shortage by State (200+ docs)
│    ├─ OSL Shortages
│    └─ JSA State Shortage Ratings
│
├─── PHASE 4: Employment (300+ docs)
│    └─ Vacancy rates and employment levels
│
├─── PHASE 5: Education (200+ docs)
│    └─ Degree requirements per ANZSCO
│
├─── PHASE 6: Migration Quotas (100+ docs)
│    ├─ State-specific (190/491)
│    └─ National ceilings
│
├─── PHASE 7: Demographics (500+ docs)
│    └─ Workforce age/gender profiles
│
├─── PHASE 8: Job Ads (300+ docs)
│    └─ Monthly IVI (Internet Vacancy Index)
│
├─── PHASE 9: Top Occupations (300+ docs)
│    └─ High-demand and fast-growth rankings
│
├─── PHASE 10: Recruitment (200+ docs)
│    └─ Applicants per placement / experience requirements
│
├─── PHASE 11: JSA Shortage Ratings (300+ docs)
│    └─ Critical vs Major shortage categories
│
├─── PHASE 12: Employment Projections (300+ docs)
│    └─ 5-year growth trajectories
│
├─── PHASE 13: Occupational Mobility (300+ docs)
│    └─ Career transition paths
│
├─── PHASE 14: Forecasts (150+ docs)
│    └─ Probabilistic shortage outcomes 2026-2028
│
├─── PHASE 15: NERO Regional Index (200+ docs)
│    └─ Regional employment strength metrics
│
└─── PHASE 16: SA4 Regional Insights (NEW)
     └─ Suburb and micro-region specific data
```

---

## SCALE & PERFORMANCE
- **Total Documents**: ~25,382
- **Vector Storage**: ChromaDB (Persistent)
- **Embedding Model**: all-MiniLM-L6-v2 (Local)
- **Indexing Logic**: Batched chunking (100 docs per chunk) with metadata inheritance.

---

## METADATA TAGS (For Intelligent Filtering)
- `category`: [occupations, shortage, employment, education_fields, migration_quotas, demographics, job_advertisements, top_occupations, recruitment, jsa_shortage, employment_projection, mobility, migration_forecast, shortage_forecast, nero_index, regional_areas]
- `occupation`: [ANZSCO Name]
- `state`: [NSW, VIC, QLD, WA, SA, TAS, ACT, NT]
- `source`: [Originating database table]
