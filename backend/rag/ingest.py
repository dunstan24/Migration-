import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from db.mysql_wrapper import get_mysql_wrapper, SqliteToMysqlWrapper
from db.database import sync_engine
from config import settings
"""
rag/ingest.py - COMPLETE DATABASE INGESTION
All 20 database tables loaded into RAG ChromaDB
15 phases of document ingestion (~12,000+ documents)
"""
import logging
from pathlib import Path
from typing import List, Dict
from rag.chroma_client import get_or_create_collection, add_documents, clear_collection

logger = logging.getLogger(__name__)
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "warehouse.db"


# Migration knowledge base documents
DEFAULT_POLICY_DOCS = [
    {
        'id': 'visa_190_vs_491_differences',
        'text': 'Visa 190 (Skilled Nominated) is a permanent visa requiring state sponsorship (5 extra points). Visa 491 (Regional) is provisional 5-year visa with regional sponsorship (15 extra points). 491 leads to Permanent Residency (Visa 191) after 3 years in regional area. 190 grants permanent residency immediately.',
        'metadata': {'category': 'visa_types', 'comparison': '190_vs_491'}
    },
    {
        'id': 'shortage_occupations_states',
        'text': 'NSW and VIC have most shortage occupations. Critical needs: Software Engineers, Registered Nurses. QLD has shortages in Construction trades. Regional areas need healthcare and education professionals.',
        'metadata': {'category': 'occupations', 'status': 'shortage'}
    },
    {
        'id': 'eoi_points_cutoff',
        'text': 'EOI points cutoff for Visa 190 ranges 65-85 points. Visa 189 independent requires 95+ points. State sponsorship reduces points needed.',
        'metadata': {'category': 'eoi_skillselect', 'type': 'cutoff_points'}
    },
    {
        'id': 'highest_invitation_rate',
        'text': 'Highest invitation rates: Healthcare (90%), Education (85%), Construction (80%). IT and Engineering require 85-95 points.',
        'metadata': {'category': 'skillselect', 'type': 'invitation_rates'}
    },
    {
        'id': 'nero_index',
        'text': 'NERO measures regional employment stability. Higher NERO score indicates stronger regional market. Used to prioritize Visa 491 regional nominations.',
        'metadata': {'category': 'indices', 'type': 'NERO'}
    },
    {
        'id': 'visa_189',
        'text': 'Visa 189 Skilled Independent: Permanent visa, points test 65+ (cutoff 95+), no sponsor required, live anywhere in Australia, 10-12 months processing.',
        'metadata': {'category': 'visa_types', 'visa': '189'}
    },
    {
        'id': 'points_system',
        'text': 'Points: Age (max 30), English (max 20), Experience (max 20), Qualifications (max 15), State sponsorship (5).',
        'metadata': {'category': 'points_system'}
    },
    {
        'id': 'visa_processing',
        'text': 'Processing times: Visa 189 (10-12 months), Visa 190 (3-6 months), Visa 491 (4-8 months).',
        'metadata': {'category': 'processing'}
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
            eoi_count = int(row['eoi_count'] or 0)
            avg_pts = round(float(row['avg_points'] or 0), 1)
            max_pts = int(row['max_points'] or 0)
            
            docs.append({
                'id': f'phase2_occupation_{occ_name.replace(" ", "_").lower()}',
                'text': f'{occ_name}: {eoi_count} EOI applications, avg {avg_pts} points, max {max_pts} points. Part of Skilled Occupation List.',
                'metadata': {
                    'category': 'occupations',
                    'occupation': occ_name,
                    'eoi_count': eoi_count,
                    'avg_points': avg_pts,
                    'source': 'eoi_records'
                }
            })
        
        conn.close()
        logger.info(f"Phase 2: Loaded {len(docs)} occupations")
        return docs
    except Exception as e:
        logger.error(f"Phase 2 failed: {e}")
        return []


def load_shortage_data_from_db() -> List[Dict]:
    """Load occupation shortage status with state information"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT DISTINCT occupation_name, skill_level_desc,
                   nsw, vic, qld, sa, wa, tas, nt, act, YEAR
            FROM osl_shortage
            WHERE occupation_name != ''
            ORDER BY YEAR DESC
        ''')
        
        docs = []
        seen_occs = set()
        
        for row in cur.fetchall():
            occ_name = row['occupation_name']
            if occ_name not in seen_occs:
                skill_level = row['skill_level_desc']
                year = int(row['YEAR'] or 0)
                
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
                    'id': f'phase3_shortage_{occ_name.replace(" ", "_").lower()}',
                    'text': f'{occ_name} ({skill_level}): Shortage in {states_str} - Year {year}. Higher visa success rates.',
                    'metadata': {
                        'category': 'shortage',
                        'occupation': occ_name,
                        'skill_level': skill_level,
                        'shortage_states': states_str,
                        'year': year,
                        'source': 'osl_shortage'
                    }
                })
                seen_occs.add(occ_name)
        
        conn.close()
        logger.info(f"Phase 3: Loaded {len(docs)} shortage records")
        return docs
    except Exception as e:
        logger.error(f"Phase 3 failed: {e}")
        return []


def load_shortage_unified_from_db() -> List[Dict]:
    """Load unified shortage data (OSL + Forecast) from MySQL"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        # Load both OSL historical and forecast data
        cur.execute('''
            SELECT anzsco_code, occupation_name, skill_level, year, state,
                   is_shortage, prob_shortage, source
            FROM shortage_unified
            WHERE occupation_name != ''
            ORDER BY year DESC, anzsco_code
        ''')
        
        docs = []
        seen_keys = set()
        
        for row in cur.fetchall():
            code = row['anzsco_code']
            occ_name = row['occupation_name']
            year = int(row['year'] or 0)
            state = row['state']
            skill_level = row['skill_level']
            is_shortage = row['is_shortage']
            prob = row['prob_shortage']
            source = row['source']
            
            # Create unique key for deduplication
            doc_key = f"{code}_{state}_{year}"
            if doc_key in seen_keys:
                continue
            seen_keys.add(doc_key)
            
            # Build text based on source
            if source == 'osl' and is_shortage:
                text = f'{occ_name} ({code}): **SHORTAGE** in {state} as of {year}. Level {skill_level}. High sponsorship potential.'
            elif source == 'forecast' and prob and prob >= 0.65:
                text = f'{occ_name} ({code}): **HIGH RISK** shortage in {state} ({year}) - Forecast probability {prob:.1%}. Plan visa applications strategically.'
            elif source == 'forecast' and prob and prob >= 0.40:
                text = f'{occ_name} ({code}): Medium shortage risk in {state} ({year}) - Forecast probability {prob:.1%}. Monitor trends.'
            elif source == 'osl+forecast':
                risk = "HIGH" if (is_shortage or (prob and prob >= 0.65)) else "MEDIUM"
                text = f'{occ_name} ({code}): {risk} shortage in {state}. Historical (OSL {year}) + Forecast confirmed. Strong visa pathway.'
            else:
                text = f'{occ_name} ({code}): Shortage status in {state} ({year}). Check sponsorship eligibility.'
            
            docs.append({
                'id': f'phase_shortage_unified_{code}_{state}_{year}'.lower(),
                'text': text,
                'metadata': {
                    'category': 'shortage_unified',
                    'occupation': occ_name,
                    'code': code,
                    'state': state,
                    'year': year,
                    'skill_level': skill_level,
                    'is_shortage': is_shortage,
                    'prob_shortage': prob,
                    'source': source
                }
            })
        
        conn.close()
        logger.info(f"Phase 3b: Loaded {len(docs)} unified shortage records")
        return docs
    except Exception as e:
        logger.error(f"Phase 3b failed: {e}")
        return []


def load_employment_data_from_db() -> List[Dict]:
    """Load employment data from quarterly employment stats"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT DISTINCT anzsco_name, SUM(employment) as total_employment,
                   AVG(vacancy_rate) as avg_vacancy
            FROM jsa_quarterly_employment
            WHERE anzsco_name != ''
            GROUP BY anzsco_name
            ORDER BY total_employment DESC
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            emp_count = int(row['total_employment'] or 0)
            vacancy_rate = round(float(row['avg_vacancy'] or 0) * 100, 1)
            
            docs.append({
                'id': f'phase4_employment_{occ_name.replace(" ", "_").lower()}',
                'text': f'{occ_name}: {emp_count:,} employment, {vacancy_rate}% vacancy rate. Strong demand indicates sponsorship opportunities.',
                'metadata': {
                    'category': 'employment',
                    'occupation': occ_name,
                    'employment_level': emp_count,
                    'vacancy_rate': vacancy_rate,
                    'source': 'jsa_quarterly_employment'
                }
            })
        
        conn.close()
        logger.info(f"Phase 4: Loaded {len(docs)} employment records")
        return docs
    except Exception as e:
        logger.error(f"Phase 4 failed: {e}")
        return []


def load_education_fields_from_db() -> List[Dict]:
    """Load education field requirements"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT anzsco_name, GROUP_CONCAT(field || ' (' || edu_level || '): ' || ROUND(share*100, 1) || '%', '; ') as education_summary
            FROM jsa_education
            WHERE anzsco_name != '' AND field != ''
            GROUP BY anzsco_name
            ORDER BY anzsco_name
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            education_summary = row['education_summary']
            
            if education_summary:
                docs.append({
                    'id': f'phase5_education_{occ_name.replace(" ", "_").lower()}',
                    'text': f'{occ_name} - Education: {education_summary}',
                    'metadata': {
                        'category': 'education_fields',
                        'occupation': occ_name,
                        'source': 'jsa_education'
                    }
                })
        
        conn.close()
        logger.info(f"Phase 5: Loaded {len(docs)} education records")
        return docs
    except Exception as e:
        logger.error(f"Phase 5 failed: {e}")
        return []


def load_migration_quotas_from_db() -> List[Dict]:
    """Load migration quota statistics - State and National"""
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
        ''')
        
        for row in cur.fetchall():
            state = row['state']
            visa_type = row['visa_type']
            quota_amount = int(row['quota_amount'] or 0)
            planning_year = row['planning_year']
            
            docs.append({
                'id': f'phase6_quotas_{state.lower()}_{visa_type}_{planning_year}',
                'text': f'{state} {visa_type} Quota: {quota_amount} places in {planning_year}. Affects nomination chances.',
                'metadata': {
                    'category': 'migration_quotas',
                    'state': state,
                    'visa_type': visa_type,
                    'quota_amount': quota_amount,
                    'source': 'state_nomination_quotas'
                }
            })
        
        # NATIONAL QUOTAS
        cur.execute('''
            SELECT visa_stream, visa_category, quota_amount, planning_year
            FROM national_migration_quotas
        ''')
        
        for row in cur.fetchall():
            visa_stream = row['visa_stream']
            visa_category = row['visa_category']
            quota_amount = int(row['quota_amount'] or 0)
            planning_year = row['planning_year']
            
            docs.append({
                'id': f'phase6_national_quotas_{visa_stream}_{visa_category}_{planning_year}',
                'text': f'National {visa_stream} {visa_category}: {quota_amount} places in {planning_year}.',
                'metadata': {
                    'category': 'migration_quotas',
                    'visa_stream': visa_stream,
                    'visa_category': visa_category,
                    'quota_amount': quota_amount,
                    'source': 'national_migration_quotas'
                }
            })
        
        conn.close()
        logger.info(f"Phase 6: Loaded {len(docs)} quota records")
        return docs
    except Exception as e:
        logger.error(f"Phase 6 failed: {e}")
        return []


def load_demographics_from_db() -> List[Dict]:
    """Load occupation demographics"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT anzsco_name, category, COUNT(DISTINCT segment) as segment_count, AVG(share) as avg_share
            FROM jsa_demographics
            WHERE anzsco_name != ''
            GROUP BY anzsco_name, category
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            category = row['category']
            
            docs.append({
                'id': f'phase7_demographics_{occ_name.replace(" ", "_").lower()}_{category.replace(" ", "_").lower()}',
                'text': f'{occ_name} ({category}): Demographic data available.',
                'metadata': {
                    'category': 'demographics',
                    'occupation': occ_name,
                    'occ_category': category,
                    'source': 'jsa_demographics'
                }
            })
        
        conn.close()
        logger.info(f"Phase 7: Loaded {len(docs)} demographic records")
        return docs
    except Exception as e:
        logger.error(f"Phase 7 failed: {e}")
        return []


def load_monthly_job_ads_from_db() -> List[Dict]:
    """Load job advertisement activity"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT anzsco_name, occ_group, AVG(job_ads_count) as avg_ads
            FROM jsa_monthly_ads
            WHERE anzsco_name != ''
            GROUP BY anzsco_name
            ORDER BY avg_ads DESC
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            avg_ads = int(row['avg_ads'] or 0)
            
            docs.append({
                'id': f'phase8_job_ads_{occ_name.replace(" ", "_").lower()}',
                'text': f'{occ_name}: ~{avg_ads} job ads monthly. High demand indicates sponsorship opportunities.',
                'metadata': {
                    'category': 'job_advertisements',
                    'occupation': occ_name,
                    'avg_ads': avg_ads,
                    'source': 'jsa_monthly_ads'
                }
            })
        
        conn.close()
        logger.info(f"Phase 8: Loaded {len(docs)} job ad records")
        return docs
    except Exception as e:
        logger.error(f"Phase 8 failed: {e}")
        return []


def load_top_occupations_from_db() -> List[Dict]:
    """Load top occupation rankings"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT DISTINCT anzsco_name, rank_category
            FROM jsa_top10
            WHERE anzsco_name != ''
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            rank_cat = row['rank_category']
            
            docs.append({
                'id': f'phase9_top_occ_{occ_name.replace(" ", "_").lower()}_{rank_cat}',
                'text': f'{occ_name}: Top occupation ({rank_cat}). High demand, better visa prospects.',
                'metadata': {
                    'category': 'top_occupations',
                    'occupation': occ_name,
                    'rank_category': rank_cat,
                    'source': 'jsa_top10'
                }
            })
        
        conn.close()
        logger.info(f"Phase 9: Loaded {len(docs)} top occupation records")
        return docs
    except Exception as e:
        logger.error(f"Phase 9 failed: {e}")
        return []


def load_recruitment_data_from_db() -> List[Dict]:
    """Load recruitment and placement data"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT DISTINCT anzsco_name, filled_vacancies, avg_applicants, pct_require_exp
            FROM jsa_recruitment
            WHERE anzsco_name != ''
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            filled = int(row['filled_vacancies'] or 0)
            applicants = int(row['avg_applicants'] or 0)
            pct_exp = int(row['pct_require_exp'] or 0)
            
            docs.append({
                'id': f'phase10_recruitment_{occ_name.replace(" ", "_").lower()}',
                'text': f'{occ_name}: {filled} filled vacancies, {applicants} avg applicants, {pct_exp}% require experience.',
                'metadata': {
                    'category': 'recruitment',
                    'occupation': occ_name,
                    'filled_vacancies': filled,
                    'source': 'jsa_recruitment'
                }
            })
        
        conn.close()
        logger.info(f"Phase 10: Loaded {len(docs)} recruitment records")
        return docs
    except Exception as e:
        logger.error(f"Phase 10 failed: {e}")
        return []


def load_jsa_shortage_ratings_from_db() -> List[Dict]:
    """Load JSA shortage ratings"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT DISTINCT anzsco_name, shortage_rating
            FROM jsa_shortage
            WHERE anzsco_name != ''
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            rating = row['shortage_rating']
            
            docs.append({
                'id': f'phase11_jsa_shortage_{occ_name.replace(" ", "_").lower()}',
                'text': f'{occ_name}: JSA shortage rating {rating}. Affects visa prospects.',
                'metadata': {
                    'category': 'jsa_shortage',
                    'occupation': occ_name,
                    'shortage_rating': rating,
                    'source': 'jsa_shortage'
                }
            })
        
        conn.close()
        logger.info(f"Phase 11: Loaded {len(docs)} JSA shortage records")
        return docs
    except Exception as e:
        logger.error(f"Phase 11 failed: {e}")
        return []


def load_projected_employment_from_db() -> List[Dict]:
    """Load projected employment"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT DISTINCT anzsco_name, projected_year, projected_change
            FROM jsa_projected
            WHERE anzsco_name != '' AND projected_change != ''
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ_name = row['anzsco_name']
            proj_year = int(row['projected_year'] or 0)
            change = row['projected_change']
            
            docs.append({
                'id': f'phase12_projected_{occ_name.replace(" ", "_").lower()}_{proj_year}',
                'text': f'{occ_name} ({proj_year}): Projected {change}. Strong growth improves visa prospects.',
                'metadata': {
                    'category': 'employment_projection',
                    'occupation': occ_name,
                    'projected_year': proj_year,
                    'source': 'jsa_projected'
                }
            })
        
        conn.close()
        logger.info(f"Phase 12: Loaded {len(docs)} projection records")
        return docs
    except Exception as e:
        logger.error(f"Phase 12 failed: {e}")
        return []


def load_mobility_data_from_db() -> List[Dict]:
    """Load occupational mobility"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        cur.execute('''
            SELECT name_origin, name_dest, mobility_type, SUM(people_movement) as total_people
            FROM jsa_mobility
            WHERE name_origin != '' AND name_dest != ''
            GROUP BY name_origin, name_dest, mobility_type
            ORDER BY total_people DESC
        ''')
        
        docs = []
        for row in cur.fetchall():
            origin = row['name_origin']
            dest = row['name_dest']
            people = int(row['total_people'] or 0)
            
            mob_type = row['mobility_type'].replace(" ", "_").lower()
            docs.append({
                'id': f'phase13_mobility_{origin.replace(" ", "_").lower()}_{dest.replace(" ", "_").lower()}_{mob_type}',
                'text': f'Occupational mobility: {origin} to {dest} ({people} people). Career transitions available.',
                'metadata': {
                    'category': 'mobility',
                    'origin': origin,
                    'destination': dest,
                    'people_movement': people,
                    'source': 'jsa_mobility'
                }
            })
        
        conn.close()
        logger.info(f"Phase 13: Loaded {len(docs)} mobility records")
        return docs
    except Exception as e:
        logger.error(f"Phase 13 failed: {e}")
        return []


def load_forecasts_from_db() -> List[Dict]:
    """Load migration and shortage forecasts"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        docs = []
        
        # MIGRATION FORECASTS
        cur.execute('''
            SELECT DISTINCT month, year, ROUND(yhat) as forecast
            FROM migration_volume_forecast
            ORDER BY year DESC
        ''')
        
        for row in cur.fetchall():
            month = row['month']
            year = int(row['year'] or 0)
            forecast = int(row['forecast'] or 0)
            
            docs.append({
                'id': f'phase14_migration_forecast_{year}_{month}',
                'text': f'Migration forecast {month} {year}: ~{forecast} volume.',
                'metadata': {
                    'category': 'migration_forecast',
                    'month': month,
                    'year': year,
                    'source': 'migration_volume_forecast'
                }
            })
        
        # SHORTAGE FORECASTS
        cur.execute('''
            SELECT DISTINCT occupation, state, ROUND(prob_2028*100) as prob_2028
            FROM shortage_forecast
            WHERE occupation != ''
            ORDER BY prob_2028 DESC
        ''')
        
        for row in cur.fetchall():
            occ_name = row['occupation']
            state = row['state']
            prob = int(row['prob_2028'] or 0)
            
            docs.append({
                'id': f'phase14_shortage_forecast_{occ_name.replace(" ", "_").lower()}_{state}',
                'text': f'{occ_name} in {state}: {prob}% shortage probability 2028.',
                'metadata': {
                    'category': 'shortage_forecast',
                    'occupation': occ_name,
                    'state': state,
                    'source': 'shortage_forecast'
                }
            })
        
        conn.close()
        logger.info(f"Phase 14: Loaded {len(docs)} forecast records")
        return docs
    except Exception as e:
        logger.error(f"Phase 14 failed: {e}")
        return []


def load_nero_index_from_db() -> List[Dict]:
    """Load NERO regional employment index"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        docs = []
        
        # NERO NORTHERN
        cur.execute('''
            SELECT DISTINCT anzsco4_name, year, AVG(nero_estimate) as avg_nero
            FROM nero_northern
            WHERE anzsco4_name != ''
            GROUP BY anzsco4_name, year
            ORDER BY year DESC
        ''')
        
        for row in cur.fetchall():
            occ_name = row['anzsco4_name']
            year = int(row['year'] or 0)
            nero = int(row['avg_nero'] or 0)
            
            docs.append({
                'id': f'phase15_nero_northern_{occ_name.replace(" ", "_").lower()}_{year}',
                'text': f'{occ_name} Northern Au {year}: NERO index {nero}. Regional employment strength.',
                'metadata': {
                    'category': 'nero_index',
                    'region': 'Northern',
                    'occupation': occ_name,
                    'year': year,
                    'source': 'nero_northern'
                }
            })
        
        # NERO REGIONAL
        cur.execute('''
            SELECT DISTINCT anzsco4_name, year, AVG(nero_estimate) as avg_nero
            FROM nero_regional
            WHERE anzsco4_name != ''
            GROUP BY anzsco4_name, year
            ORDER BY year DESC
        ''')
        
        for row in cur.fetchall():
            occ_name = row['anzsco4_name']
            year = int(row['year'] or 0)
            nero = int(row['avg_nero'] or 0)
            
            docs.append({
                'id': f'phase15_nero_regional_{occ_name.replace(" ", "_").lower()}_{year}',
                'text': f'{occ_name} Regional Au {year}: NERO index {nero}. Regional visa eligibility.',
                'metadata': {
                    'category': 'nero_index',
                    'region': 'Regional',
                    'occupation': occ_name,
                    'year': year,
                    'source': 'nero_regional'
                }
            })
        
        # SA4 LOOKUP
        cur.execute('''
            SELECT DISTINCT sa4_name, jsa_remoteness
            FROM nero_sa4_lookup
            WHERE sa4_name != ''
        ''')
        
        for row in cur.fetchall():
            sa4_name = row['sa4_name']
            remoteness = row['jsa_remoteness']
            
            docs.append({
                'id': f'phase15_sa4_lookup_{sa4_name.replace(" ", "_").lower()}',
                'text': f'{sa4_name} ({remoteness}): Regional area for Visa 491.',
                'metadata': {
                    'category': 'regional_areas',
                    'sa4_area': sa4_name,
                    'source': 'nero_sa4_lookup'
                }
            })
        
        conn.close()
        logger.info(f"Phase 15: Loaded {len(docs)} NERO/regional records")
        return docs
    except Exception as e:
        logger.error(f"Phase 15 failed: {e}")
        return []


def load_sa4_regional_insights_from_db() -> List[Dict]:
    """Phase 16: Load localized regional employment estimates from nero_sa4 joined with remoteness lookups"""
    try:
        conn = get_mysql_wrapper(settings)
        # Row factory handled by DictCursor
        cur = conn.cursor()
        
        # We aggregate by SA4 and Occupation across months to keep doc count manageable but comprehensive
        cur.execute('''
            SELECT s.sa4_name, s.anzsco4_name, s.state_name, l.jsa_remoteness,
                   AVG(s.nsc_emp) as avg_employment, MAX(s.year) as latest_year
            FROM nero_sa4 s
            JOIN nero_sa4_lookup l ON s.sa4_code = l.sa4_code
            WHERE s.anzsco4_name != '' AND s.sa4_name != ''
            GROUP BY s.sa4_name, s.anzsco4_name
            HAVING avg_employment > 10
            ORDER BY avg_employment DESC
        ''')
        
        docs = []
        for row in cur.fetchall():
            occ = row['anzsco4_name']
            region = row['sa4_name']
            state = row['state_name']
            remoteness = row['jsa_remoteness'] or "Regional"
            emp = int(row['avg_employment'] or 0)
            
            docs.append({
                'id': f'phase16_sa4_{occ.replace(" ", "_").lower()}_{region.replace(" ", "_").lower()}',
                'text': f'{occ} in {region}, {state} ({remoteness}): Estimated local employment of {emp}. High regional relevance for Visa 491/190.',
                'metadata': {
                    'category': 'regional_insight',
                    'occupation': occ,
                    'region': region,
                    'remoteness': remoteness,
                    'employment': emp,
                    'source': 'nero_sa4'
                }
            })
            
        conn.close()
        logger.info(f"Phase 16: Loaded {len(docs)} SA4 regional insights")
        return docs
    except Exception as e:
        logger.error(f"Phase 16 failed: {e}")
        return []


def load_website_context() -> List[Dict]:
    """Phase 17: Load website context from text file"""
    try:
        from pathlib import Path
        context_path = Path(__file__).resolve().parent.parent / "data" / "website_context.txt"
        
        if not context_path.exists():
            logger.warning(f"Website context file not found at {context_path}")
            return []
            
        content = context_path.read_text(encoding='utf-8')
        
        blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
        
        docs = []
        for i, block in enumerate(blocks):
            title = block.split(':', 1)[0].strip() if ':' in block else f"Website Topic {i+1}"
            docs.append({
                'id': f'phase17_website_{title.replace(" ", "_").lower()}',
                'text': block,
                'metadata': {
                    'category': 'website_knowledge',
                    'title': title,
                    'source': 'website_context.txt'
                }
            })
            
        logger.info(f"Phase 17: Loaded {len(docs)} website knowledge blocks")
        return docs
    except Exception as e:
        logger.error(f"Phase 17 failed: {e}")
        return []

def ingest_migration_documents():
    """Complete database ingestion - all 16 phases"""
    try:
        collection = get_or_create_collection("migration-docs")
        logger.info("🔄 Clearing existing ChromaDB...")
        clear_collection(collection)
        
        all_docs = []
        breakdown = {}
        
        # PHASE 1
        logger.info(f"📄 Phase 1: {len(DEFAULT_POLICY_DOCS)} policy docs...")
        all_docs.extend(DEFAULT_POLICY_DOCS)
        breakdown['phase_1_policy'] = len(DEFAULT_POLICY_DOCS)
        
        # PHASES 2-16
        phases = [
            ("💼 Phase 2: Occupations", load_occupations_from_db),
            ("⚠️  Phase 3: Shortage (OSL)", load_shortage_data_from_db),
            ("⚠️  Phase 3b: Shortage Unified", load_shortage_unified_from_db),
            ("📊 Phase 4: Employment", load_employment_data_from_db),
            ("🎓 Phase 5: Education", load_education_fields_from_db),
            ("🏛️  Phase 6: Quotas", load_migration_quotas_from_db),
            ("👥 Phase 7: Demographics", load_demographics_from_db),
            ("📢 Phase 8: Job Ads", load_monthly_job_ads_from_db),
            ("⭐ Phase 9: Top Occs", load_top_occupations_from_db),
            ("🤝 Phase 10: Recruitment", load_recruitment_data_from_db),
            ("📈 Phase 11: JSA Shortage", load_jsa_shortage_ratings_from_db),
            ("📡 Phase 12: Projections", load_projected_employment_from_db),
            ("🔄 Phase 13: Mobility", load_mobility_data_from_db),
            ("🔮 Phase 14: Forecasts", load_forecasts_from_db),
            ("📍 Phase 15: NERO", load_nero_index_from_db),
            ("🗺️  Phase 16: SA4 Regional", load_sa4_regional_insights_from_db),
            ("🌐 Phase 17: Website Context", load_website_context),
        ]
        
        for phase_name, loader_func in phases:
            logger.info(phase_name)
            docs = loader_func()
            all_docs.extend(docs)
            phase_key = phase_name.split(':')[1].strip().replace(' ', '_').lower()
            breakdown[f'phase_{len(breakdown)}_' + phase_key] = len(docs)
        
        # INGEST ALL
        logger.info(f"🚀 Ingesting {len(all_docs)} total documents...")
        add_documents(collection, all_docs)
        logger.info(f"✅ Success!")
        
        return {
            "status": "success",
            "total_documents": len(all_docs),
            "breakdown": breakdown
        }
    except Exception as e:
        logger.error(f"❌ Ingestion failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e)
        }


def get_collection():
    """Get the migration documents collection"""
    return get_or_create_collection("migration-docs")
