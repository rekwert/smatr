# Re-export celery app for `celery -A app.workers.celery_app`
from app.workers.celery_app import celery_app, scan_market, run_backtest

__all__ = ["celery_app", "scan_market", "run_backtest"]
