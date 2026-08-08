import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
def load_data_from_db():
    print("This script is obsolete. The project now uses MySQL only.")
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

    conn = get_mysql_wrapper(settings)
    query = """
    SELECT
        anzsco_code  AS occupation,
        state,
        COALESCE(points, 65) AS points,
        visa_type
    FROM eoi_records
    WHERE eoi_status IN ('SUBMITTED', 'INVITED', 'LODGED')
      AND anzsco_code IS NOT NULL
      AND state IS NOT NULL
      AND points IS NOT NULL
    ORDER BY RANDOM()
    LIMIT 30000
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        raise ValueError("No records found in eoi_records table.")

    logger.info(f"Loaded {len(df)} raw records from DB.")

    # ── Normalise visa_type to '189' / '190' / '491'
    def visa_clean(v):
        v = str(v)
        if '189' in v: return '189'
        if '190' in v: return '190'
        if '491' in v: return '491'
        return None

    df['visa_clean'] = df['visa_type'].apply(visa_clean)
    df = df[df['visa_clean'].notna()].copy()

    # ── Normalise state
    df['state'] = df['state'].where(df['state'].isin(VALID_STATES))
    df = df[df['state'].notna()].copy()

    # ── Clamp points to realistic range
    df['points'] = df['points'].clip(lower=0, upper=140).astype(int)

    # ── Build target label
    df['target'] = df.apply(
        lambda r: '189_National' if r['visa_clean'] == '189'
                  else f"{r['visa_clean']}_{r['state']}",
        axis=1
    )

    # ── Boost 189 representation if heavily underrepresented
    count_189 = (df['visa_clean'] == '189').sum()
    if count_189 < 500:
        logger.info(f"Only {count_189} visa-189 records. Injecting balanced 189 samples ...")
        base = df[df['visa_clean'] == '190'].copy()
        if base.empty:
            base = df.copy()
        n = min(2000, max(500, len(base)))
        s189 = base.sample(n, replace=True).copy()
        s189['target']     = '189_National'
        s189['visa_clean'] = '189'
        s189['state']      = 'National'
        # 189 typically requires higher points than 190/491
        s189['points']     = (s189['points'] + np.random.choice([5, 10, 15], n, p=[0.3, 0.5, 0.2])).clip(0, 140)
        df = pd.concat([df, s189], ignore_index=True)
        logger.info(f"Dataset after 189 injection: {len(df)} rows.")

    logger.info(f"Final training set: {len(df)} rows — class distribution:\n{df['target'].value_counts().head(20)}")
    return df


def train_model(data_path=None):
    # ── Load data
    if data_path and os.path.exists(data_path):
        logger.info(f"Loading features from CSV: {data_path}")
        df = pd.read_csv(data_path)
    else:
        logger.warning("Feature CSV not found — falling back to warehouse.db.")
        df = load_data_from_db()

    # ── Features: occupation, state, points only
    # (english/age/experience are already encoded within the points score)
    FEATURES = ["occupation", "state", "points"]
    TARGET   = "target"

    for col in FEATURES + [TARGET]:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' missing from training data.")

    df = df.dropna(subset=FEATURES + [TARGET]).copy()

    X = df[FEATURES]
    y = df[TARGET]

    logger.info(f"Training on {len(X)} samples, {y.nunique()} target classes.")

    # ── Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # ── Preprocessing
    preprocessor = ColumnTransformer(transformers=[
        ('num', StandardScaler(),                     ["points"]),
        ('cat', OneHotEncoder(handle_unknown='ignore'), ["occupation", "state"]),
    ])

    # ── Pipeline
    pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('model', GradientBoostingClassifier(
            n_estimators=150,
            learning_rate=0.08,
            max_depth=5,
            subsample=0.8,
            min_samples_leaf=5,
            random_state=42,
        ))
    ])

    # ── 5-Fold Cross Validation
    logger.info("Running 5-Fold Cross Validation ...")
    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_results = cross_validate(
        pipeline, X, y, cv=cv,
        scoring=['accuracy', 'f1_macro', 'precision_macro', 'recall_macro']
    )
    logger.info(f"CV Accuracy:  {np.mean(cv_results['test_accuracy']):.4f} (+/- {np.std(cv_results['test_accuracy']):.4f})")
    logger.info(f"CV F1-Macro:  {np.mean(cv_results['test_f1_macro']):.4f}")
    logger.info(f"CV Precision: {np.mean(cv_results['test_precision_macro']):.4f}")
    logger.info(f"CV Recall:    {np.mean(cv_results['test_recall_macro']):.4f}")

    # ── Final fit
    logger.info("Fitting final model on training split ...")
    pipeline.fit(X_train, y_train)

    # ── Evaluate
    y_pred = pipeline.predict(X_test)
    acc    = accuracy_score(y_test, y_pred)
    logger.info(f"Test Accuracy: {acc:.4f}")
    logger.info("\nClassification Report:\n" + classification_report(y_test, y_pred))

    # ── SHAP (optional)
    try:
        import shap
        logger.info("Computing SHAP feature importances ...")
        X_pre   = pipeline.named_steps['preprocessor'].transform(X_test.iloc[:200])
        explainer = shap.TreeExplainer(pipeline.named_steps['model'])
        shap_vals = explainer.shap_values(X_pre)
        logger.info(f"SHAP computed for {len(shap_vals) if isinstance(shap_vals, list) else 1} class(es).")
    except ImportError:
        logger.warning("SHAP not installed — skipping (pip install shap).")
    except Exception as e:
        logger.warning(f"SHAP failed: {e}")

    # ── Save
    os.makedirs(os.path.dirname(MODEL_SAVE_PATH), exist_ok=True)
    joblib.dump(pipeline, MODEL_SAVE_PATH)
    logger.info(f"Model saved → {MODEL_SAVE_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=DEFAULT_FEATURES_CSV, help="Path to features CSV")
    args = parser.parse_args()

    try:
        train_model(args.data)
    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
