with open('ingest.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all ID patterns with phase-prefixed versions
replacements = [
    ("'id': f'occupation_", "'id': f'phase2_occupation_"),
    ("'id': f'shortage_", "'id': f'phase3_shortage_"),
    ("'id': f'employment_", "'id': f'phase4_employment_"),
    ("'id': f'education_", "'id': f'phase5_education_"),
    ("'id': f'quotas_", "'id': f'phase6_quotas_"),
    ("'id': f'national_quotas_", "'id': f'phase6_national_quotas_"),
    ("'id': f'demographics_", "'id': f'phase7_demographics_"),
    ("'id': f'job_ads_", "'id': f'phase8_job_ads_"),
    ("'id': f'top_occ_", "'id': f'phase9_top_occ_"),
    ("'id': f'recruitment_", "'id': f'phase10_recruitment_"),
    ("'id': f'jsa_shortage_", "'id': f'phase11_jsa_shortage_"),
    ("'id': f'projected_", "'id': f'phase12_projected_"),
    ("'id': f'mobility_", "'id': f'phase13_mobility_"),
    ("'id': f'migration_forecast_", "'id': f'phase14_migration_forecast_"),
    ("'id': f'shortage_forecast_", "'id': f'phase14_shortage_forecast_"),
    ("'id': f'nero_northern_", "'id': f'phase15_nero_northern_"),
    ("'id': f'nero_regional_", "'id': f'phase15_nero_regional_"),
    ("'id': f'sa4_lookup_", "'id': f'phase15_sa4_lookup_"),
]

for old, new in replacements:
    if old in content:
        count = content.count(old)
        content = content.replace(old, new)
        print(f"Replaced {count} instances of {old}")

with open('ingest.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✓ Updated all IDs with phase numbers")
