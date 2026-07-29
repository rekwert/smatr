# Re-export tasks module path expected by Celery beat
from app.workers.celery_app import run_backtest, scan_market, universe_scan

__all__ = ["scan_market", "run_backtest", "universe_scan"]
