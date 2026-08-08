

@router.get("/data")
async def get_report_data(
    months:        int = Query(6),
    visa_type:     str = Query("491"),
    occupation:    str = Query(""),
    state:         str = Query("NSW"),
    points:        int = Query(80),
    english_level: str = Query("proficient"),
    age:           int = Query(30),
    experience:    int = Query(5),
    count_eois:    int = Query(100),
    db: AsyncSession = Depends(get_db),
):
    """Return report data as JSON (for testing and frontend integration)"""
    try:
        report_data = await _fetch_report_data(
            months, visa_type, occupation, state, points,
            english_level, age, experience, count_eois, db
        )
        return report_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"Error fetching report data: {str(e)}")
