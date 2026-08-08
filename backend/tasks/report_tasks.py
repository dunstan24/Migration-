"""
tasks/report_tasks.py
Celery async tasks for PPT/PDF generation per README:
  python-pptx → branded Inter PowerPoint
  WeasyPrint  → HTML → PDF report card
  LLM writes slide copy via Claude
"""
import os
from celery import Celery
from config import settings

celery_app = Celery(
    "interlace",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    timezone="Australia/Sydney",
    enable_utc=True,
)


@celery_app.task(bind=True)
def generate_report_task(self, report_type: str, date_from: str, date_to: str):
    """
    Async Celery job:
    1. Query DB for filtered data
    2. Call Claude to generate slide copy
    3. Build PPT (python-pptx) or PDF (WeasyPrint)
    4. Return download path
    Sprint 6 implementation.
    """
    self.update_state(state="PROGRESS", meta={"step": "fetching_data"})
    # TODO Sprint 6: implement full pipeline
    return {
        "status": "done",
        "report_type": report_type,
        "download_url": f"/reports/{self.request.id}.pdf",
    }
