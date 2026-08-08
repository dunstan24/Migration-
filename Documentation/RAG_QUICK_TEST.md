# RAG Quick Reference - Test Questions

## QUICK TEST QUESTIONS (Copy & Paste)

### 1. OCCUPATIONS (All 491 available)

```
Q: How many occupations do you have in the database?
Expected: 491 occupations with details

Q: Tell me about Software Engineers
Expected: EOI count, average points, shortage status

Q: What about Registered Nurses?
Expected: Demand, employment data, regional availability

Q: Can you list the top 10 hardest occupations to get visas for?
Expected: High point requirements, competition level

Q: Which occupations have the most job ads?
Expected: Top 10 by job advertisement volume monthly
```

### 2. SHORTAGE DATA (By State & Occupation)

```
Q: Which occupations are in shortage in NSW?
Expected: List of shortage occupations with states affected

Q: Tell me about healthcare shortages
Expected: Nurses, Aged Care, Paramedics shortage status

Q: What's the shortage situation for IT roles in Victoria?
Expected: Software Engineers, Systems Managers shortage status

Q: Will there still be nursing shortages in 2028?
Expected: Probability forecast for future years
```

### 3. VISA INFORMATION

```
Q: What's the difference between Visa 190 and Visa 491?
Expected: Main differences, permanent vs temporary, points

Q: How long does Visa 190 take to process?
Expected: 3-6 months typical processing time

Q: Do I need a sponsor for Visa 189?
Expected: No sponsor needed, points test only 95+

Q: How much experience do I need?
Expected: Max 20 points for experience category
```

### 4. POINTS SYSTEM

```
Q: How many points do I need for skilled migration?
Expected: 65 points minimum, 95+ for 189, 85 for 190

Q: Break down the points calculation for me
Expected: Age, English, Experience, Qualifications, State sponsorship

Q: What occupations have the highest average scores?
Expected: Various occupations with average EOI points
```

### 5. EMPLOYMENT & JOB MARKET

```
Q: What's the job market like for nurses?
Expected: 650+ ads monthly, 90% invitation rate, strong demand

Q: How many Software Engineer jobs are there?
Expected: 450+ ads monthly, vacancy rates, competition level

Q: Which jobs have the most vacancies?
Expected: Healthcare highest, then IT, then Construction

Q: How many applicants per job?
Expected: 85+ average applicants per position
```

### 6. REGIONAL & VISA 491

```
Q: What regions are good for Visa 491?
Expected: Newcastle, Canberra, regional areas with NERO scores

Q: Where can I work as a nurse regionally?
Expected: Far North Queensland, Regional NSW opportunities

Q: What's NERO and why does it matter?
Expected: Employment stability measure, higher = better regional job prospects

Q: Can I do Software Engineering work regionally?
Expected: Canberra (tech hub), Newcastle, Brisbane region
```

### 7. GROWTH & PROJECTIONS

```
Q: Which occupations will grow the most by 2028?
Expected: Healthcare +18%, IT +14%, Construction +12%

Q: What's the employment outlook for Data Scientists?
Expected: +22% growth projected (highest tech role)

Q: Will IT stay in shortage?
Expected: 80%+ probability through 2028
```

### 8. EDUCATION & QUALIFICATIONS

```
Q: What degree do I need to be a Software Engineer?
Expected: Computer Science or Engineering degree required

Q: Can I work as a nurse with just a diploma?
Expected: Bachelor required for visa sponsorship in most states

Q: What's the education requirement for accountants?
Expected: Bachelor in Accounting or related field
```

### 9. QUOTAS & COMPETITION

```
Q: How many places does NSW have for state sponsorship?
Expected: Visa 190: 1,250, Visa 491: 800 places

Q: How many places available nationwide?
Expected: Varies by visa type and year

Q: How competitive is it to get selected?
Expected: Depends on occupation, higher competition for popular roles
```

### 10. CAREER TRANSITIONS

```
Q: Can I transition from IT to Data Science?
Expected: 3,200+ annual transitions, 78% success rate

Q: Can nurses move into management?
Expected: 320+ transitions to health management annually
```

---

## TIPS FOR BETTER RESULTS

1. **Be Specific**: "Software Engineers in NSW" better than just "engineers"
2. **Ask About States**: Each state has different shortages and quotas
3. **Mention Visas**: "For Visa 190..." vs generic question
4. **Comparative Questions**: "Which occupation has better prospects, A or B?"
5. **Time-Based**: "By 2028, what's the outlook for...?"
6. **Market Research**: "What's the job market like for...?"

---

## EXPECTED RESPONSE PATTERNS

The AI will typically say:

- "According to our database..." → Using real data
- "We have 491 occupations..." → Found complete occupation list
- "...average points, max points" → Showing statistics
- "Shortage in [State]..." → Regional data
- "...% probability by 2028" → Forecasts
- "Top occupations by..." → Rankings

GOOD SIGN: If AI is specific with numbers and states
BAD SIGN: If AI gives only 4-5 items when you asked for "all available"

---

## CURRENT RAG STATISTICS

- **Total Documents**: ~4,200
- **Occupations Indexed**: 491
- **Shortage Occupations by State**: 200+
- **Employment Records**: 300+
- **Regional Areas**: 100+
- **Forecast Records**: 150+
- **Coverage**: All 20 database tables

---

## RECENT FIXES

✅ **Fixed**: Occupation retrieval now returns ALL 491 instead of just 4
✅ **Fixed**: Database metadata filtering working correctly
✅ **Fixed**: State and regional data properly indexed
✅ **Testing**: Run test questions above to verify all data is accessible
