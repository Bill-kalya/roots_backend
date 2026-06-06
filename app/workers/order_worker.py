import logging

logger = logging.getLogger(__name__)


class _StubTask:
    """Celery stub — replace with real @celery_app.task when Celery is configured."""

    def apply_async(self, args=None, kwargs=None, countdown=None, **kw):
        logger.warning(
            "Celery not configured. Skipping background task args=%s countdown=%ss",
            args,
            countdown,
        )


cancel_expired_order = _StubTask()
fulfill_order = _StubTask()

