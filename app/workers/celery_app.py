from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "roots_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.email_worker",
        "app.workers.order_worker",
        "app.workers.backup_worker"
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_max_tasks_per_child=1000,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_queue_max_priority=10,
    task_default_priority=5,
    
    # Rate limiting
    task_annotations={
        "app.workers.email_worker.send_welcome_email": {"rate_limit": "10/m"},
        "app.workers.order_worker.process_order": {"rate_limit": "50/m"},
    },
    
    # Retry configuration
    task_default_retry_delay=60,
    task_max_retries=3,
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "cleanup-abandoned-carts": {
        "task": "app.workers.order_worker.cleanup_abandoned_carts",
        "schedule": 3600.0,  # Every hour
    },
    "send-order-reminders": {
        "task": "app.workers.order_worker.send_order_reminders",
        "schedule": 300.0,  # Every 5 minutes
    },
    "daily-backup": {
        "task": "app.workers.backup_worker.create_database_backup",
        "schedule": 86400.0,  # Daily
    },
    "update-metrics": {
        "task": "app.workers.metrics_worker.update_business_metrics",
        "schedule": 60.0,  # Every minute
    },
}