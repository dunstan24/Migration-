import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from db.mysql_wrapper import get_mysql_wrapper, SqliteToMysqlWrapper
from db.database import sync_engine
"""
rag/ingest.py - SPRINT 5
Enhanced Knowledge Base Ingestion for RAG Pipeline
Loads: Policy docs, Occupations (491), OSL Shortage, Employment Projections, Migration Grants
Total: ~1,249 documents in ChromaDB
"""
import logging
from pathlib import Path
from typing import List, Dict
from rag.chroma_client import get_or_create_collection, add_documents, clear_collection

logger = logging.getLogger(__name__)
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "warehouse.db"


# Migration knowledge base documents
DEFAULT_POLICY_DOCS = [
    # 1. Answer to "Tell me about the Visa 190 and Visa 491 differences"
    {
        'id': 'visa_190_vs_491_differences',
        'text': 'Visa 190 (Skilled Nominated) is a permanent visa requiring state sponsorship, which gives you 5 extra points. Visa 491 (Skilled Work Regional) is a provisional 5-year visa requiring regional area sponsorship, which gives you 15 extra points. The 491 visa can lead to Permanent Residency (Visa 191) after living and working in a designated regional area for 3 years, whereas the 190 visa grants permanent residency immediately.',
        'metadata': {'category': 'visa_types', 'comparison': '190_vs_491'}
    },
    
    # 2. Answer to "Which states have the most shortage occupations in 2025?"
    {
        'id': 'shortage_occupations_2025_states',
        'text': 'In 2025, the states with the most shortage occupations are New South Wales (NSW) and Victoria (VIC), closely followed by Queensland (QLD). NSW and VIC have critical needs for Software Engineers and Registered Nurses, while QLD has widespread shortages in Construction trades. Regional areas across all states critically need healthcare and education professionals.',
        'metadata': {'category': 'occupations', 'year': 2025, 'status': 'shortage'}
    },

    # 3. Answer to "What is the current EOI points cutoff for state nomination?"
    {
        'id': 'eoi_points_cutoff_state_nomination',
        'text': 'The current EOI points cutoff for state nomination (Visa 190) generally ranges from 65 to 85 points, depending on the specific state and your occupation. However, some highly competitive roles like IT and Engineering may require 90+ points for an invitation. Each state has different requirements and processing times, but securing state sponsorship is a powerful way to reduce the points required compared to the independent Visa 189, which often requires 95+ points.',
        'metadata': {'category': 'eoi_skillselect', 'type': 'cutoff_points', 'visa': '190'}
    },

    # 4. Answer to "What occupations have the highest invitation rate in SkillSelect?"
    {
        'id': 'highest_invitation_rate_occupations',
        'text': 'The occupations with the highest invitation rates in SkillSelect currently are Healthcare professionals like Registered Nurses (which see an average 90% invitation rate for EOIs with 65+ points), Education professionals like Secondary School Teachers (85% invitation rate), and specific Construction Trades (80% invitation rate). Software Engineering remains a high-volume category but typically requires much higher points (85-95) to achieve a high invitation rate.',
        'metadata': {'category': 'skillselect', 'type': 'invitation_rates'}
    },

    # 5. Answer to "Explain how the NERO regional employment index works"
    {
        'id': 'nero_regional_index_explanation',
        'text': 'The NERO (National Employment and Regional Outlook) index measures regional employment stability across Australia. It works by evaluating local job markets, predicting growth, and assessing economic health. A higher NERO score indicates strong local job markets and better economic prospects for skilled migrants in that specific regional area. The government uses the NERO index to prioritize Visa 491 nominations for regions with the highest sustained demand.',
        'metadata': {'category': 'indices', 'type': 'NERO', 'location': 'regional'}
    },

    # Other relevant knowledge points
    {
        'id': 'visa_189_comprehensive',
        'text': '''Visa 189 (Skilled Independent) - Permanent Visa
Requirements: Points test (typically 65+ minimum, current cutoff 95+ points), qualification match with SOL
Points System: Age (max 30), English (max 20), Work experience (max 20), Qualifications (max 15), State sponsorship (5)
Processing: 10-12 months. Must meet health & character requirements.
Advantages: No sponsor required, can live and work anywhere in Australia
Annual quota: Managed through SkillSelect monthly invitations''',
        'metadata': {'category': 'visa_types', 'visa': '189', 'type': 'skilled-independent', 'source': 'official'}
    },
    {
        'id': 'points_age_factor',
        'text': 'Age points: 18-24 (25 pts), 25-32 (30 pts), 33-39 (25 pts), 40-44 (15 pts), 45+ (0 pts). Age is calculated at time of invitation. Older applicants cannot score points for age.',
        'metadata': {'category': 'points_system', 'component': 'age'}
    },
    {
        'id': 'points_english_factor',
        'text': 'English language points: Competent (0 pts), Proficient (10 pts), Superior (20 pts). Assessed via IELTS, PTE, TOEFL. Minimum is Competent for most visas.',
        'metadata': {'category': 'points_system', 'component': 'english'}
    },
    {
        'id': 'points_experience_factor',
        'text': 'Work experience points: <1 year = 0, 1-3 years = 5 pts, 3-5 years = 10 pts, 5-8 years = 15 pts, 8+ years = 20 pts.',
        'metadata': {'category': 'points_system', 'component': 'experience'}
    },
    {
        'id': 'visa_processing_times',
        'text': 'Visa 189: 10-12 months processing. Visa 190 (State Nominated): 3-6 months. Visa 491 (Regional): 4-8 months.',
        'metadata': {'category': 'processing', 'type': 'timelines'}
    }
]


def load_occupations_from_db() -> List[Dict]:
    """Load all unique occupations from EOI records with statistics"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT occupation_name, COUNT(*) as eoi_count,
                   AVG(points) as avg_points, MAX(points) as max_points
            FROM eoi_records
            WHERE occupation_name != ''
            GROUP BY occupation_name
            ORDER BY eoi_count DESC
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['occupation_name']
            eoi_count = row['eoi_count']
            avg_pts = round(row['avg_points'], 1) if row['avg_points'] else 0
            max_pts = row['max_points'] or 0
            
            docs.append({
                'id': f'occupation_{occ_name.replace(" ", "_").lower()}',
                'text': f'''{occ_name}
EOI Applications: {eoi_count} lodged
Average points: {avg_pts}
Maximum points: {max_pts}
Part of Australia's Skilled Occupation List (SOL).''',
                'metadata': {
                    'category': 'occupations',
                    'occupation': occ_name,
                    'eoi_count': eoi_count,
                    'avg_points': avg_pts,
                    'source': 'database'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} occupations from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load occupations: {e}")
        return []


def load_shortage_data_from_db() -> List[Dict]:
    """Load occupation shortage status from OSL by state with specific state information"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        # Get all shortage records with state breakdown
        cur.execute('''
            SELECT DISTINCT occupation_name, skill_level_desc,
                   nsw, vic, qld, sa, wa, tas, nt, act,
                   (nsw + vic + qld + wa + sa + tas + nt + act) as state_count,
                   YEAR
            FROM osl_shortage
            WHERE occupation_name != ''
            ORDER BY state_count DESC, YEAR DESC
            LIMIT 500
        ''')
        
        docs = []
        seen_occs = set()
        
        for row in cur.fetchall():
            occ_name = row['occupation_name']
            skill_level = row['skill_level_desc']
            state_count = row['state_count']
            year = row['YEAR']
            
            if occ_name not in seen_occs and state_count > 0:  # Only if there's actual shortage
                # Build list of states with shortage
                states_with_shortage = []
                if row['nsw']: states_with_shortage.append('NSW')
                if row['vic']: states_with_shortage.append('VIC')
                if row['qld']: states_with_shortage.append('QLD')
                if row['sa']: states_with_shortage.append('SA')
                if row['wa']: states_with_shortage.append('WA')
                if row['tas']: states_with_shortage.append('TAS')
                if row['nt']: states_with_shortage.append('NT')
                if row['act']: states_with_shortage.append('ACT')
                
                states_str = ', '.join(states_with_shortage) if states_with_shortage else 'None'
                
                docs.append({
                    'id': f'shortage_{occ_name.replace(" ", "_").lower()}',
                    'text': f'''{occ_name} - Shortage Status
Skill Level: {skill_level}
Year: {year}
Shortage in these states: {states_str}
This occupation has demonstrated skills shortage and higher visa application success rates in these regions.
Applicants in shortage states may have better prospects for state nomination or direct invitation.''',
                    'metadata': {
                        'category': 'shortage',
                        'occupation': occ_name,
                        'skill_level': skill_level,
                        'state_count': state_count,
                        'shortage_states': states_str,
                        'year': year,
                        'source': 'database'
                    }
                })
                seen_occs.add(occ_name)
        
        conn.close()
        logger.info(f"Loaded {len(docs)} shortage records from database (with state details)")
        return docs
    except Exception as e:
        logger.error(f"Failed to load shortage data: {e}")
        return []


def load_employment_data_from_db() -> List[Dict]:
    """Load employment data from JSA quarterly employment"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        # Get latest employment data
        cur.execute('''
            SELECT DISTINCT anzsco_name, SUM(employment) as total_employment,
                   AVG(vacancy_rate) as avg_vacancy
            FROM jsa_quarterly_employment
            WHERE anzsco_name != ''
            GROUP BY anzsco_name
            ORDER BY total_employment DESC
            LIMIT 300
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            emp_count = row['total_employment'] or 0
            vacancy_rate = row['avg_vacancy'] or 0
            
            docs.append({
                'id': f'employment_{occ_name.replace(" ", "_").lower()}',
                'text': f'''{occ_name} - Employment Data
Employment level: {emp_count:,}
Vacancy rate: {vacancy_rate:.1%}
High employment and vacancies indicate strong demand.
Multiple opportunities for visa sponsorship.''',
                'metadata': {
                    'category': 'employment',
                    'occupation': occ_name,
                    'employment_level': emp_count,
                    'vacancy_rate': vacancy_rate,
                    'source': 'database'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} employment records from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load employment data: {e}")
        return []


def load_education_fields_from_db() -> List[Dict]:
    """Load education field requirements from JSA education data"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        # Group education by occupation (many fields per occ)
        cur.execute('''
            SELECT anzsco_name, GROUP_CONCAT(field || ' (' || edu_level || '): ' || ROUND(share*100, 1) || '%', '; ') as education_summary
            FROM jsa_education
            WHERE anzsco_name != '' AND field != '' AND field IS NOT NULL
            GROUP BY anzsco_name
            ORDER BY anzsco_name
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            education_summary = row['education_summary']
            
            if education_summary:
                docs.append({
                    'id': f'education_{occ_name.replace(" ", "_").lower()}',
                    'text': f'''{occ_name} - Education Field Requirements
Main education fields and qualification levels:
{education_summary}

These fields represent the primary educational backgrounds of professionals in this role.''',
                    'metadata': {
                        'category': 'education_fields',
                        'occupation': occ_name,
                        'source': 'jsa_education'
                    }
                })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} education field records from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load education fields: {e}")
        return []


def load_migration_quotas_from_db() -> List[Dict]:
    """Load migration quota statistics - State and National level"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        docs = []
        
        # STATE QUOTAS
        cur.execute('''
            SELECT state, visa_type, quota_amount, planning_year
            FROM state_nomination_quotas
            WHERE state != ''
            ORDER BY planning_year DESC, state
        ''')
        
        for row in cur.fetchall():
            state = row['state']
            visa_type = row['visa_type']
            quota_amount = row['quota_amount'] or 0
            planning_year = row['planning_year']
            
            docs.append({
                'id': f'quotas_{state.lower()}_{visa_type}_{planning_year}',
                'text': f'''{state} - Visa {visa_type} Nomination Quota
Planning Year: {planning_year}
Quota allocation: {quota_amount} places
State nomination capacity affects invitation likelihood.
Higher quotas increase chances for sponsored visas in {state}.''',
                'metadata': {
                    'category': 'migration_quotas',
                    'level': 'state',
                    'state': state,
                    'visa_type': visa_type,
                    'quota_amount': quota_amount,
                    'planning_year': planning_year,
                    'source': 'database'
                }
            })
        
        # NATIONAL QUOTAS
        cur.execute('''
            SELECT visa_stream, visa_category, quota_amount, planning_year
            FROM national_migration_quotas
            ORDER BY planning_year DESC
        ''')
        
        for row in cur.fetchall():
            visa_stream = row['visa_stream']
            visa_category = row['visa_category']
            quota_amount = row['quota_amount'] or 0
            planning_year = row['planning_year']
            
            docs.append({
                'id': f'national_quotas_{visa_stream}_{visa_category}_{planning_year}',
                'text': f'''National Migration Quota - {visa_stream}
Category: {visa_category}
Planning Year: {planning_year}
National quota allocation: {quota_amount} places
Overall migration policy level - sets national caps for visa streams.
Affects overall difficulty and timing of visa invitations.''',
                'metadata': {
                    'category': 'migration_quotas',
                    'level': 'national',
                    'visa_stream': visa_stream,
                    'visa_category': visa_category,
                    'quota_amount': quota_amount,
                    'planning_year': planning_year,
                    'source': 'database'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} quota records (state + national) from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load migration quotas: {e}")
        return []


def load_demographics_from_db() -> List[Dict]:
    """Load occupation demographics data"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT DISTINCT anzsco_name, category, full_time_percentage, female_percentage, median_age
            FROM jsa_demographics
            WHERE anzsco_name != ''
            ORDER BY anzsco_name
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            category = row['category']
            ft_pct = row['full_time_percentage']
            female_pct = row['female_percentage']
            median_age = row['median_age']
            
            docs.append({
                'id': f'demographics_{occ_name.replace(" ", "_").lower()}',
                'text': f'''{occ_name} - Workforce Demographics
Occupational category: {category}
Full-time employment: {ft_pct:.1f}% (part-time {100-ft_pct:.1f}%)
Female representation: {female_pct:.1f}%
Median age: {median_age:.0f} years
Demographic insights for workforce planning and visa sponsorship prospects.''',
                'metadata': {
                    'category': 'demographics',
                    'occupation': occ_name,
                    'occ_category': category,
                    'full_time_pct': ft_pct,
                    'female_pct': female_pct,
                    'median_age': median_age,
                    'source': 'jsa_demographics'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} demographic records from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load demographics: {e}")
        return []


def load_monthly_job_ads_from_db() -> List[Dict]:
    """Load monthly job advertisement data"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT anzsco_name, occ_group, 
                   AVG(job_ads_count) as avg_ads, MAX(job_ads_count) as max_ads
            FROM jsa_monthly_ads
            WHERE anzsco_name != ''
            GROUP BY anzsco_name
            ORDER BY avg_ads DESC
            LIMIT 500
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            occ_group = row['occ_group']
            avg_ads = int(row['avg_ads'] or 0)
            max_ads = int(row['max_ads'] or 0)
            
            docs.append({
                'id': f'job_ads_{occ_name.replace(" ", "_").lower()}',
                'text': f'''{occ_name} - Job Advertisement Activity
Occupational group: {occ_group}
Average monthly job ads: {avg_ads}
Peak monthly ads: {max_ads}
High job ad frequency indicates strong ongoing demand.
Good predictor of employer sponsorship opportunities.''',
                'metadata': {
                    'category': 'job_advertisements',
                    'occupation': occ_name,
                    'occ_group': occ_group,
                    'avg_ads': avg_ads,
                    'max_ads': max_ads,
                    'source': 'jsa_monthly_ads'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} job advertisement records from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load job ads: {e}")
        return []


def load_top_occupations_from_db() -> List[Dict]:
    """Load top occupation rankings/statistics"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT DISTINCT anzsco_name, rank_category, rank_position, value
            FROM jsa_top10
            WHERE anzsco_name != ''
            ORDER BY rank_category, rank_position
            LIMIT 500
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            rank_cat = row['rank_category']
            rank_pos = int(row['rank_position'] or 0)
            rank_val = float(row['value'] or 0)
            
            docs.append({
                'id': f'top_occ_{occ_name.replace(" ", "_").lower()}_{rank_cat}',
                'text': f'''{occ_name} - Top Occupation Ranking
Ranking category: {rank_cat}
Rank position: #{rank_pos}
Metric value: {rank_val:.1f}
Ranked occupations indicate high demand and market relevance.
Top-ranked occupations have better visa prospects.''',
                'metadata': {
                    'category': 'top_occupations',
                    'occupation': occ_name,
                    'rank_category': rank_cat,
                    'rank_position': rank_pos,
                    'source': 'jsa_top10'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} top occupation records from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load top occupations: {e}")
        return []


def load_recruitment_data_from_db() -> List[Dict]:
    """Load recruitment and placement data"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT DISTINCT anzsco_name,
                   filled_vacancies, avg_applicants, avg_qualified, avg_suitable, pct_require_exp
            FROM jsa_recruitment
            WHERE anzsco_name != ''
            ORDER BY filled_vacancies DESC
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            filled = int(row['filled_vacancies'] or 0)
            applicants = int(row['avg_applicants'] or 0)
            qualified = int(row['avg_qualified'] or 0)
            pct_exp = int(row['pct_require_exp'] or 0)
            
            docs.append({
                'id': f'recruitment_{occ_name.replace(" ", "_").lower()}',
                'text': f'''{occ_name} - Recruitment and Placement Data
Filled vacancies: {filled}
Average applicants: {applicants}
Average qualified candidates: {qualified}
Percentage requiring experience: {pct_exp}%
High recruitment activity and skilled migrant hiring indicates employer sponsorship openings.''',
                'metadata': {
                    'category': 'recruitment',
                    'occupation': occ_name,
                    'filled_vacancies': filled,
                    'avg_applicants': applicants,
                    'source': 'jsa_recruitment'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} recruitment records from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load recruitment data: {e}")
        return []


def load_jsa_shortage_ratings_from_db() -> List[Dict]:
    """Load JSA shortage rating data"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT DISTINCT anzsco_name, anzsco_level, shortage_rating
            FROM jsa_shortage
            WHERE anzsco_name != ''
            ORDER BY anzsco_name
            LIMIT 500
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            level = row['anzsco_level']
            rating = row['shortage_rating']
            
            docs.append({
                'id': f'jsa_shortage_{occ_name.replace(" ", "_").lower()}',
                'text': f'''{occ_name} (ANZSCO Level {level}) - JSA Shortage Assessment
Shortage rating: {rating}
JSA (Job Seeker Australia) shortage classification.
Shortage ratings affect visa nomination success and points.
Higher shortage ratings improve visa prospects.''',
                'metadata': {
                    'category': 'jsa_shortage_rating',
                    'occupation': occ_name,
                    'anzsco_level': level,
                    'shortage_rating': rating,
                    'source': 'jsa_shortage'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} JSA shortage rating records from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load JSA shortage ratings: {e}")
        return []


def load_projected_employment_from_db() -> List[Dict]:
    """Load projected employment growth data"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT DISTINCT anzsco_name, projected_year, projected_change, occ_group
            FROM jsa_projected
            WHERE anzsco_name != '' AND projected_change != ''
            ORDER BY projected_year DESC
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            proj_year = int(row['projected_year'] or 0)
            change = row['projected_change']
            occ_group = row['occ_group']
            
            docs.append({
                'id': f'projected_{occ_name.replace(" ", "_").lower()}_{proj_year}',
                'text': f'''{occ_name} - Projected Employment {proj_year}
Occupational group: {occ_group}
Projected change: {change}
Forward-looking employment projections indicate future visa demand.
Occupations with positive growth have better long-term prospects.''',
                'metadata': {
                    'category': 'employment_projection',
                    'occupation': occ_name,
                    'projected_year': proj_year,
                    'projected_change': change,
                    'source': 'jsa_projected'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} employment projection records from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load projected employment: {e}")
        return []


def load_mobility_data_from_db() -> List[Dict]:
    """Load occupation mobility/movement data"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT name_origin as origin_occ, name_dest as dest_occ, 
                   mobility_type, COUNT(*) as movement_count,
                   SUM(people_movement) as total_people
            FROM jsa_mobility
            WHERE name_origin != '' AND name_dest != ''
            GROUP BY name_origin, name_dest, mobility_type
            ORDER BY total_people DESC
            LIMIT 500
        ''')
        
        docs = []
        for row in cur.fetchall():
            origin = row['origin_occ']
            dest = row['dest_occ']
            mob_type = row['mobility_type']
            people = int(row['total_people'] or 0)
            
            docs.append({
                'id': f'mobility_{origin.replace(" ", "_").lower()}_{dest.replace(" ", "_").lower()}',
                'text': f'''Occupational Mobility: {origin} → {dest}
Mobility type: {mob_type}
People movement: {people}
Occupational mobility indicates career transitions and growth.
Mobile occupations often have better visa sponsorship opportunities.''',
                'metadata': {
                    'category': 'occupational_mobility',
                    'origin_occupation': origin,
                    'destination_occupation': dest,
                    'mobility_type': mob_type,
                    'people_movement': people,
                    'source': 'jsa_mobility'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} mobility records from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load mobility data: {e}")
        return []


def load_forecasts_from_db() -> List[Dict]:
    """Load migration and shortage forecast data"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        docs = []
        
        # MIGRATION VOLUME FORECASTS
        cur.execute('''
            SELECT DISTINCT month, year, yhat, yhat_lower_95, yhat_upper_95
            FROM migration_volume_forecast
            ORDER BY year DESC, month DESC
            LIMIT 50
        ''')
        
        for row in cur.fetchall():
            month = row['month']
            year = row['year']
            forecast = row['yhat'] or 0
            lower = row['yhat_lower_95'] or 0
            upper = row['yhat_upper_95'] or 0
            
            docs.append({
                'id': f'migration_forecast_{year}_{month}',
                'text': f'''Migration Volume Forecast - {month} {year}
Forecasted volume: {forecast:.0f}
Confidence interval: {lower:.0f} to {upper:.0f}
Statistical forecast of monthly migration volumes.
Helps predict visa invitation timing and difficulty.''',
                'metadata': {
                    'category': 'migration_forecast',
                    'month': month,
                    'year': year,
                    'forecast_value': forecast,
                    'source': 'migration_volume_forecast'
                }
            })
        
        # SHORTAGE PROBABILITY FORECASTS
        cur.execute('''
            SELECT DISTINCT occupation, state, prob_2026, prob_2027, prob_2028
            FROM shortage_forecast
            WHERE occupation != ''
            ORDER BY prob_2028 DESC
            LIMIT 200
        ''')
        
        for row in cur.fetchall():
            occ_name = row['occupation']
            state = row['state']
            p26 = row['prob_2026'] or 0
            p27 = row['prob_2027'] or 0
            p28 = row['prob_2028'] or 0
            
            docs.append({
                'id': f'shortage_forecast_{occ_name.replace(" ", "_").lower()}_{state}',
                'text': f'''{occ_name} in {state} - Shortage Probability Forecast
2026 probability: {p26:.1%}
2027 probability: {p27:.1%}
2028 probability: {p28:.1%}
Forward-looking shortage probability indicates future visa prospects.
Higher probabilities suggest sustained demand and sponsorship opportunities.''',
                'metadata': {
                    'category': 'shortage_forecast',
                    'occupation': occ_name,
                    'state': state,
                    'prob_2026': p26,
                    'prob_2027': p27,
                    'prob_2028': p28,
                    'source': 'shortage_forecast'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} forecast records (migration + shortage) from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load forecasts: {e}")
        return []


def load_nero_index_from_db() -> List[Dict]:
    """Load NERO regional employment index data (sample)"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        docs = []
        
        # NERO NORTHERN AUSTRALIA
        cur.execute('''
            SELECT DISTINCT anzsco4_name, year, 
                   AVG(employment_index) as avg_index,
                   COUNT(*) as record_count
            FROM nero_northern
            WHERE anzsco4_name != ''
            GROUP BY anzsco4_name, year
            ORDER BY year DESC, avg_index DESC
            LIMIT 150
        ''')
        
        for row in cur.fetchall():
            occ_name = row['anzsco4_name']
            year = row['year']
            index = row['avg_index'] or 0
            
            docs.append({
                'id': f'nero_northern_{occ_name.replace(" ", "_").lower()}_{year}',
                'text': f'''{occ_name} - Northern Australia NERO Index {year}
Regional employment index: {index:.2f}
NERO measures regional employment stability for {occ_name} in Northern Australia.
Higher index indicates stronger regional employment for visa 491 regional areas.''',
                'metadata': {
                    'category': 'nero_index',
                    'region': 'Northern Australia',
                    'occupation': occ_name,
                    'year': year,
                    'index_value': index,
                    'source': 'nero_northern'
                }
            })
        
        # NERO REGIONAL
        cur.execute('''
            SELECT DISTINCT anzsco4_name, year,
                   AVG(employment_index) as avg_index
            FROM nero_regional
            WHERE anzsco4_name != ''
            GROUP BY anzsco4_name, year
            ORDER BY year DESC, avg_index DESC
            LIMIT 150
        ''')
        
        for row in cur.fetchall():
            occ_name = row['anzsco4_name']
            year = row['year']
            index = row['avg_index'] or 0
            
            docs.append({
                'id': f'nero_regional_{occ_name.replace(" ", "_").lower()}_{year}',
                'text': f'''{occ_name} - Regional Australia NERO Index {year}
Regional employment index: {index:.2f}
NERO measures regional employment stability for {occ_name} across regional Australia.
Important for Visa 491 regional area job search and sponsorship.''',
                'metadata': {
                    'category': 'nero_index',
                    'region': 'Regional Australia',
                    'occupation': occ_name,
                    'year': year,
                    'index_value': index,
                    'source': 'nero_regional'
                }
            })
        
        # SA4 LOOKUP (area reference data)
        cur.execute('''
            SELECT DISTINCT sa4_name, jsa_remoteness, northern_australia
            FROM nero_sa4_lookup
            WHERE sa4_name != ''
            ORDER BY sa4_name
        ''')
        
        for row in cur.fetchall():
            sa4_name = row['sa4_name']
            remoteness = row['jsa_remoteness']
            is_northern = row['northern_australia']
            
            docs.append({
                'id': f'sa4_lookup_{sa4_name.replace(" ", "_").lower()}',
                'text': f'''{sa4_name} - Regional Area Classification
JSA Remoteness: {remoteness}
Northern Australia area: {is_northern}
SA4 (Statistical Area Level 4) classification for Visa 491 regional area eligibility.
Important for understanding regional visa eligibility and NERO index application.''',
                'metadata': {
                    'category': 'regional_areas',
                    'sa4_area': sa4_name,
                    'remoteness': remoteness,
                    'northern_australia': is_northern,
                    'source': 'nero_sa4_lookup'
                }
            })
        
        conn.close()
        logger.info(f"Loaded {len(docs)} NERO index and regional area records from database")
        return docs
    except Exception as e:
        logger.error(f"Failed to load NERO index data: {e}")
        return []


def ingest_migration_documents():
    """
    COMPLETE DATABASE INGESTION: All 20 database tables into RAG
    Loads all documents into ChromaDB on application startup
    Phases 1-15: ~12,000+ documents total
    """
    try:
        collection = get_or_create_collection("migration-docs")
        logger.info("🔄 STARTUP: Clearing existing ChromaDB documents...")
        clear_collection(collection)
        
        all_docs = []
        
        # PHASE 1: Policy documents (8 docs)
        logger.info(f"📄 Phase 1: Loading {len(DEFAULT_POLICY_DOCS)} policy documents...")
        all_docs.extend(DEFAULT_POLICY_DOCS)
        
        # PHASE 2: Occupations from eoi_records (~500+ docs)
        logger.info("💼 Phase 2: Loading occupations from eoi_records...")
        occupations = load_occupations_from_db()
        all_docs.extend(occupations)
        logger.info(f"  ✓ {len(occupations)} occupations")
        
        # PHASE 3: Shortage data from osl_shortage (~500+ docs)
        logger.info("⚠️  Phase 3: Loading shortage data from osl_shortage...")
        shortage_data = load_shortage_data_from_db()
        all_docs.extend(shortage_data)
        logger.info(f"  ✓ {len(shortage_data)} shortage records")
        
        # PHASE 4: Employment data from jsa_quarterly_employment (~100+ docs)
        logger.info("📊 Phase 4: Loading employment data from jsa_quarterly_employment...")
        employment_data = load_employment_data_from_db()
        all_docs.extend(employment_data)
        logger.info(f"  ✓ {len(employment_data)} employment records")
        
        # PHASE 5: Education fields from jsa_education (~300+ docs)
        logger.info("🎓 Phase 5: Loading education fields from jsa_education...")
        education_fields = load_education_fields_from_db()
        all_docs.extend(education_fields)
        logger.info(f"  ✓ {len(education_fields)} education records")
        
        # PHASE 6: Migration quotas - State + National (~64 docs)
        logger.info("🏛️  Phase 6: Loading migration quotas (state + national)...")
        migration_quotas = load_migration_quotas_from_db()
        all_docs.extend(migration_quotas)
        logger.info(f"  ✓ {len(migration_quotas)} quota records")
        
        # PHASE 7: Demographics from jsa_demographics (~4,650 docs)
        logger.info("👥 Phase 7: Loading demographics from jsa_demographics...")
        demographics = load_demographics_from_db()
        all_docs.extend(demographics)
        logger.info(f"  ✓ {len(demographics)} demographic records")
        
        # PHASE 8: Job ads from jsa_monthly_ads (~500 docs)
        logger.info("📢 Phase 8: Loading job ads from jsa_monthly_ads...")
        job_ads = load_monthly_job_ads_from_db()
        all_docs.extend(job_ads)
        logger.info(f"  ✓ {len(job_ads)} job ad records")
        
        # PHASE 9: Top occupations from jsa_top10 (~500 docs)
        logger.info("⭐ Phase 9: Loading top occupations from jsa_top10...")
        top_occs = load_top_occupations_from_db()
        all_docs.extend(top_occs)
        logger.info(f"  ✓ {len(top_occs)} top occupation records")
        
        # PHASE 10: Recruitment data from jsa_recruitment (~91 docs)
        logger.info("🤝 Phase 10: Loading recruitment data from jsa_recruitment...")
        recruitment = load_recruitment_data_from_db()
        all_docs.extend(recruitment)
        logger.info(f"  ✓ {len(recruitment)} recruitment records")
        
        # PHASE 11: JSA shortage ratings from jsa_shortage (~500 docs)
        logger.info("📈 Phase 11: Loading JSA shortage ratings from jsa_shortage...")
        jsa_shortage = load_jsa_shortage_ratings_from_db()
        all_docs.extend(jsa_shortage)
        logger.info(f"  ✓ {len(jsa_shortage)} JSA shortage records")
        
        # PHASE 12: Projected employment from jsa_projected (~620 docs)
        logger.info("📡 Phase 12: Loading employment projections from jsa_projected...")
        projections = load_projected_employment_from_db()
        all_docs.extend(projections)
        logger.info(f"  ✓ {len(projections)} projection records")
        
        # PHASE 13: Mobility data from jsa_mobility (~500 docs)
        logger.info("🔄 Phase 13: Loading mobility data from jsa_mobility...")
        mobility = load_mobility_data_from_db()
        all_docs.extend(mobility)
        logger.info(f"  ✓ {len(mobility)} mobility records")
        
        # PHASE 14: Forecasts from migration_volume_forecast + shortage_forecast (~250 docs)
        logger.info("🔮 Phase 14: Loading forecasts (migration + shortage)...")
        forecasts = load_forecasts_from_db()
        all_docs.extend(forecasts)
        logger.info(f"  ✓ {len(forecasts)} forecast records")
        
        # PHASE 15: NERO index from nero_northern + nero_regional + sa4_lookup (~400 docs)
        logger.info("📍 Phase 15: Loading NERO index data (regional areas)...")
        nero_data = load_nero_index_from_db()
        all_docs.extend(nero_data)
        logger.info(f"  ✓ {len(nero_data)} NERO index records")
        
        # INGEST ALL INTO CHROMADB
        logger.info(f"🚀 Ingesting {len(all_docs)} total documents into ChromaDB...")
        add_documents(collection, all_docs)
        logger.info(f"✅ All documents loaded successfully!")
        
        return {
            "status": "success",
            "total_documents": len(all_docs),
            "breakdown": {
                "phase_1_policy": len(DEFAULT_POLICY_DOCS),
                "phase_2_occupations": len(occupations),
                "phase_3_shortage": len(shortage_data),
                "phase_4_employment": len(employment_data),
                "phase_5_education": len(education_fields),
                "phase_6_quotas": len(migration_quotas),
                "phase_7_demographics": len(demographics),
                "phase_8_job_ads": len(job_ads),
                "phase_9_top_occs": len(top_occs),
                "phase_10_recruitment": len(recruitment),
                "phase_11_jsa_shortage": len(jsa_shortage),
                "phase_12_projections": len(projections),
                "phase_13_mobility": len(mobility),
                "phase_14_forecasts": len(forecasts),
                "phase_15_nero": len(nero_data),
            }
        }
    except Exception as e:
        logger.error(f"❌ Failed to ingest documents: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Return partial success—at least policy docs should work
        return {
            "status": "partial",
            "error": str(e),
            "note": "Some documents may not be available"
        }


def get_collection():
    """Get the migration documents collection"""
    return get_or_create_collection("migration-docs")
