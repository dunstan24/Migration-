# 📊 Database Structure Guide

**Database:** SQLite (`backend/data/processed/warehouse.db`)  
**Size:** ~1-2 GB (3+ million records)  
**Purpose:** Australian migration analytics, occupational insight, and RAG knowledge base

---

## 🗂️ Table Groups & Content

### 🔷 **GROUP 1: CORE EOI DATA** (Express of Interest Applications)

#### **eoi_records** — 8 Million Rows

The heart of the system. Every SkillSelect EOI submission since 2015.

| Column            | Content           | Example                             |
| ----------------- | ----------------- | ----------------------------------- |
| `as_at_str`       | Snapshot Month    | "April 2026"                        |
| `visa_type`       | Visa code         | 189, 190, 491                       |
| `occupation_name` | Job title         | "Software Engineer"                 |
| `eoi_status`      | Application stage | SUBMITTED, INVITED, WAITLIST        |
| `points`          | Score earned      | 75, 85, 95                          |
| `count_eois`      | # of applications | 1, 5, 10                            |
| `state`           | Nominated state   | NSW, VIC, QLD, WA, SA, TAS, NT, ACT |

**Key Statistics:**

- Total applications: 8+ million
- Visa 189 (Independent): ~60%
- Visa 190 (State Sponsored): ~25%
- Visa 491 (Regional): ~15%

**Used For:**

- EOI acceptance rates by occupation
- Points cutoff analysis
- Visa subclass success trends
- State-by-state demand

---

### 🔶 **GROUP 2: JSA EMPLOYMENT DATA** (Jobs and Skills Australia)

These tables contain current employment statistics and labor market data.

#### **jsa_monthly_ads** — 20K Rows

Job advertisement data (Internet Vacancy Index)

| Column          | Content          | Example             |
| --------------- | ---------------- | ------------------- |
| `anzsco_code`   | Occupation code  | "261313"            |
| `anzsco_name`   | Occupation name  | "Software Engineer" |
| `job_ads_date`  | Month recorded   | "2026-04"           |
| `job_ads_count` | Active vacancies | 1250                |

**Used For:**

- Current job market demand
- Vacancy trends by occupation

---

#### **jsa_quarterly_employment** — 40K Rows

Quarterly employment statistics

| Column         | Content       | Example   |
| -------------- | ------------- | --------- |
| `quarter`      | Time period   | "Q1-2026" |
| `employment`   | Total workers | 45,000    |
| `vacancy_rate` | Unfilled %    | 8.5%      |

**Used For:**

- Employment growth trends
- Unemployment by occupation
- Regional labor needs

---

#### **jsa_demographics** — 4K Rows

Workforce composition by age, gender, experience

| Column     | Content         | Example                       |
| ---------- | --------------- | ----------------------------- |
| `category` | Data type       | "Age", "Gender", "Experience" |
| `segment`  | Specific bucket | "25-34", "Male", "5-10 years" |
| `share`    | Percentage      | 0.35 (35%)                    |

**Used For:**

- Age distribution analysis
- Gender breakdown in roles
- Experience requirements

---

#### **jsa_education** — 7K Rows

Education field requirements by occupation

| Column      | Content        | Example                           |
| ----------- | -------------- | --------------------------------- |
| `field`     | Study area     | "Engineering", "Computer Science" |
| `edu_level` | Qualification  | "Bachelor", "Masters", "Diploma"  |
| `share`     | % of workforce | 0.60 (60% have this field)        |

**Used For:**

- Education requirements for visa success
- Field of study matching
- Qualification demand

---

### 🔴 **GROUP 3: SHORTAGE & OPPORTUNITIES**

Identifies which occupations are in shortage and highest demand.

#### **osl_shortage** — 4K Rows

Occupation Shortage List (OSL) - Official list of shortage occupations

| Column                 | Content           | Example              |
| ---------------------- | ----------------- | -------------------- |
| `occupation_name`      | Job title         | "Registered Nurse"   |
| `skill_level_desc`     | ANZSCO level      | "Level 1", "Level 2" |
| `nsw, vic, qld, sa...` | State shortage?   | Yes/No (1/0)         |
| `national`             | National shortage | Yes/No               |

**Used For:**

- Visa 190/491 eligibility checking
- Fast-track occupations
- State sponsorship opportunities

---

#### **jsa_shortage** — 1K Rows

Jobs and Skills Australia shortage ratings

| Column            | Content         | Example                         |
| ----------------- | --------------- | ------------------------------- |
| `anzsco_code`     | Occupation code | "131112"                        |
| `shortage_rating` | Severity        | "Critical", "Major", "Minor"    |
| `shortage_driver` | Reason          | "Skills gap", "Aging workforce" |

**Used For:**

- Predicting visa invitation chances
- Understanding labor market drivers
- Policy recommendations

---

#### **jsa_top10** — 5K Rows

Top occupations by demand, growth, or earnings

| Column          | Content      | Example                            |
| --------------- | ------------ | ---------------------------------- |
| `rank_category` | Ranking type | "Highest Demand", "Fastest Growth" |
| `rank_position` | Position     | 1, 2, 3... 10                      |
| `sa4_name`      | Region       | "Inner West Sydney"                |
| `value`         | Score/metric | 95.5                               |

**Used For:**

- Identifying best occupations
- Regional opportunities
- Career planning

---

### 📈 **GROUP 4: PROJECTIONS & FORECASTS**

Predict future labor market trends and shortage probabilities.

#### **jsa_projected** — 500 Rows

5-10 year employment projections

| Column             | Content        | Example                    |
| ------------------ | -------------- | -------------------------- |
| `projected_year`   | Year           | 2028, 2030                 |
| `projected_change` | Growth/decline | "+15%", "-5%"              |
| `occ_group`        | Category       | "Healthcare", "Technology" |

**Used For:**

- Long-term career planning
- Future occupational viability

---

#### **shortage_forecast** — 7K Rows

Probabilistic forecast of which occupations will be in shortage

| Column       | Content              | Example             |
| ------------ | -------------------- | ------------------- |
| `occupation` | Job title            | "Software Engineer" |
| `state`      | State code           | "NSW", "VIC"        |
| `prob_2028`  | Shortage probability | 0.85 (85% chance)   |

**Used For:**

- Predicting future visa success
- Risk assessment
- Decision making

---

#### **migration_volume_forecast** — Historical Data

Migration intake volume forecasts

| Column            | Content          | Example    |
| ----------------- | ---------------- | ---------- |
| `month`           | Month            | "January"  |
| `year`            | Year             | 2026, 2027 |
| `forecast_volume` | Expected intakes | 2,500      |

**Used For:**

- Planning intake schedules
- Quota management

---

### 🗺️ **GROUP 5: REGIONAL ANALYSIS**

Break down employment and visa opportunities by geography.

#### **nero_regional** — 80K Rows

NERO (Network Employment and Regional Outcomes) - Regional Australia data

| Column          | Content             | Example           |
| --------------- | ------------------- | ----------------- |
| `anzsco4_name`  | 4-digit ANZSCO      | "1321" (Managers) |
| `year`          | Fiscal year         | 2025, 2026        |
| `nero_estimate` | Employment strength | 450 (workers)     |

**Used For:**

- Regional employment distribution
- Visa 491 (Regional visa) planning
- Regional nomination opportunities

---

#### **nero_northern** — 40K Rows

Northern Australia employment data (Darwin, Northern Territory focus)

**Used For:**

- Northern regional opportunities
- Remote area visa sponsorship

---

#### **nero_sa4** — 3 Million Rows

Super Area 4 (SA4) - Detailed suburb/micro-region employment

| Column           | Content          | Example                                |
| ---------------- | ---------------- | -------------------------------------- |
| `sa4_name`       | Suburb/region    | "Inner West Sydney", "Melbourne Inner" |
| `state_name`     | State            | "NSW", "VIC"                           |
| `avg_employment` | Workers in area  | 2,500                                  |
| `jsa_remoteness` | Remoteness level | "Major City", "Regional", "Remote"     |

**Used For:**

- Finding visa 491 regional opportunities
- Suburb-level employment insights
- Remote eligibility checking

---

#### **nero_sa4_lookup** — 80 Rows

Reference table: SA4 codes and names

**Used For:**

- SA4 code translations
- Regional name matching

---

### 🎯 **GROUP 6: QUOTAS & ALLOCATIONS**

Government migration quotas and caps.

#### **national_migration_quotas** — 40 Rows

Annual national migration intake targets

| Column          | Content     | Example             |
| --------------- | ----------- | ------------------- |
| `visa_stream`   | Stream type | "Skilled Migration" |
| `quota_amount`  | Annual cap  | 195,000             |
| `planning_year` | Year        | 2026                |

**Used For:**

- Understanding intake limits
- Visa availability

---

#### **state_nomination_quotas** — 10 Rows

State-specific nomination allocations

| Column         | Content       | Example      |
| -------------- | ------------- | ------------ |
| `state`        | State code    | "NSW"        |
| `visa_type`    | Visa subclass | 190, 491     |
| `quota_amount` | Allocations   | 5,000 places |

**Used For:**

- State sponsorship limits
- Competition by state
- Visa 190/491 availability

---

### 🤝 **GROUP 7: RECRUITMENT & CAREER MOBILITY**

Labor market recruitment patterns and career transitions.

#### **jsa_recruitment** — 80 Rows

Recruitment statistics and applicant behavior

| Column             | Content         | Example       |
| ------------------ | --------------- | ------------- |
| `filled_vacancies` | # hired         | 1,250         |
| `avg_applicants`   | Per position    | 45 applicants |
| `avg_qualified`    | % qualified     | 0.35 (35%)    |
| `pct_require_exp`  | Need experience | 0.80 (80%)    |

**Used For:**

- Understanding hiring difficulty
- Experience requirements
- Competition levels

---

#### **jsa_mobility** — 15K Rows

Career transition data - People moving between occupations

| Column            | Content             | Example                 |
| ----------------- | ------------------- | ----------------------- |
| `code_origin`     | Starting occupation | "261313" (Software Eng) |
| `code_dest`       | New occupation      | "131112" (Manager)      |
| `people_movement` | # who transitioned  | 250                     |

**Used For:**

- Career path analysis
- Alternative occupations
- Transition probabilities

---

## 🔗 Data Relationships

```
eoi_records (8M)
    ├─→ matches occupation codes in jsa_* tables
    ├─→ validates against osl_shortage
    ├─→ checked against state_nomination_quotas
    └─→ influences jsa_recruitment stats

jsa_monthly_ads (20K)
    ├─→ fed into shortage_forecast
    ├─→ breaks down by jsa_demographics
    └─→ shows job market demand

jsa_projected (500)
    └─→ predicts shortage_forecast outcomes

nero_sa4 (3M)
    ├─→ references nero_sa4_lookup
    ├─→ breaks down by state_name
    └─→ enables regional visa 491 planning

short_forecast (7K) + shortage_forecast (7K)
    └─→ used by RAG for occupation recommendations
```

---

## 📊 Data Volume Summary

| Group          | Tables | Total Rows | Size        |
| -------------- | ------ | ---------- | ----------- |
| Core EOI       | 1      | 8M         | ~800 MB     |
| JSA Employment | 4      | 64K        | ~50 MB      |
| Shortage       | 3      | 10K        | ~8 MB       |
| Forecasts      | 3      | 7.5K       | ~10 MB      |
| Regional       | 4      | 3.2M       | ~300 MB     |
| Quotas         | 2      | 50         | <1 MB       |
| Recruitment    | 2      | 15K        | ~2 MB       |
| **Total**      | **19** | **11.3M+** | **~1.2 GB** |

---

## 🚀 Query Examples

### Find occupations with highest visa success rate

```sql
SELECT occupation_name,
       COUNT(*) as total_eois,
       SUM(CASE WHEN eoi_status='INVITED' THEN 1 ELSE 0 END) as invited,
       (SUM(CASE WHEN eoi_status='INVITED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as success_rate
FROM eoi_records
WHERE as_at_str = 'April 2026'
GROUP BY occupation_name
ORDER BY success_rate DESC
LIMIT 10;
```

### Find occupations in shortage in NSW

```sql
SELECT occupation_name, skill_level_desc
FROM osl_shortage
WHERE nsw = 1 AND national = 1;
```

### Identify regions with high employment in regional visa zones

```sql
SELECT sa4_name, state_name, SUM(avg_employment) as total_workers
FROM nero_sa4
WHERE jsa_remoteness IN ('Regional', 'Remote')
GROUP BY sa4_name
ORDER BY total_workers DESC
LIMIT 20;
```

### Forecast shortage risk for next 2 years

```sql
SELECT occupation, state, prob_2028 as shortage_probability
FROM shortage_forecast
WHERE prob_2028 > 0.70
ORDER BY prob_2028 DESC;
```

---

## 🎯 Use Cases

1. **EOI Analysis** → Query `eoi_records` directly
2. **Market Demand** → See `jsa_monthly_ads` + `jsa_quarterly_employment`
3. **Visa Success** → Cross-reference `osl_shortage` + `state_nomination_quotas`
4. **Regional Opportunities** → Use `nero_sa4` + `jsa_top10`
5. **Career Planning** → Check `jsa_projected` + `jsa_mobility`
6. **Future Risk** → Review `shortage_forecast` + migration volumes
7. **RAG Knowledge Base** → All tables indexed and searchable

---

## 🔐 Database Integrity

- **Backup:** Multiple exports available in `backend/data/raw/`
- **Indexes:** Created on common query columns (anzsco_code, state, etc.)
- **Updates:** Refreshed monthly via data ingestion pipelines
- **Validation:** All data validated on insert (type checking, key constraints)

---

**Updated:** April 2026  
**Total Records:** 11.3+ million  
**Last Refresh:** [See logs in backend]
