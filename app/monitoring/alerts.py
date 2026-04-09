import os
import uuid
import asyncio
import logging
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFO     = "info"


class AlertType(str, Enum):
    DATABASE    = "database"
    REDIS       = "redis"
    API         = "api"
    BUSINESS    = "business"
    SECURITY    = "security"
    PERFORMANCE = "performance"


# ---------------------------------------------------------------------------
# AlertManager
# ---------------------------------------------------------------------------

class AlertManager:
    """
    Enterprise alerting system.

    Supports Slack, PagerDuty, and email channels.
    Channels are only used when their respective env vars are configured —
    the system degrades gracefully when they are absent.
    """

    # Keep only the last N alerts in memory to avoid unbounded growth
    MAX_IN_MEMORY_ALERTS = 500

    def __init__(self) -> None:
        self.alerts: List[Dict[str, Any]] = []
        self._setup_channels()

    def _setup_channels(self) -> None:
        """Read channel configuration from environment variables."""
        self.slack_webhook: Optional[str] = os.environ.get("SLACK_WEBHOOK_URL")
        self.pagerduty_key: Optional[str] = os.environ.get("PAGERDUTY_API_KEY")

        raw_emails = os.environ.get("ALERT_EMAILS", "")
        self.email_recipients: List[str] = (
            [e.strip() for e in raw_emails.split(",") if e.strip()]
            if raw_emails else []
        )

        configured = []
        if self.slack_webhook:
            configured.append("Slack")
        if self.pagerduty_key:
            configured.append("PagerDuty")
        if self.email_recipients:
            configured.append(f"Email({len(self.email_recipients)})")

        logger.info(
            "AlertManager initialised. Channels: %s",
            ", ".join(configured) if configured else "none (logging only)"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        alert_type: AlertType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build, store, and dispatch an alert through the appropriate channels.

        Routing:
          CRITICAL  → PagerDuty + Slack + Email
          HIGH      → Slack + Email
          MEDIUM    → Slack
          LOW/INFO  → log only
        """
        alert: Dict[str, Any] = {
            "id":        str(uuid.uuid4()),
            "title":     title,
            "message":   message,
            "severity":  severity.value,
            "type":      alert_type.value,
            "metadata":  metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Bounded in-memory store
        self.alerts.append(alert)
        if len(self.alerts) > self.MAX_IN_MEMORY_ALERTS:
            self.alerts = self.alerts[-self.MAX_IN_MEMORY_ALERTS:]

        log_fn = (
            logger.critical if severity == AlertSeverity.CRITICAL
            else logger.error if severity == AlertSeverity.HIGH
            else logger.warning
        )
        log_fn("Alert [%s][%s]: %s — %s", severity.value, alert_type.value, title, message)

        # Dispatch — failures in one channel must never block the others
        if severity == AlertSeverity.CRITICAL:
            await asyncio.gather(
                self._send_pagerduty(alert),
                self._send_slack(alert),
                self._send_email(alert),
                return_exceptions=True,
            )
        elif severity == AlertSeverity.HIGH:
            await asyncio.gather(
                self._send_slack(alert),
                self._send_email(alert),
                return_exceptions=True,
            )
        elif severity == AlertSeverity.MEDIUM:
            await self._send_slack(alert)

        return alert

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    async def _send_slack(self, alert: Dict[str, Any]) -> None:
        """Post a formatted message to a Slack incoming webhook."""
        if not self.slack_webhook:
            return

        try:
            import aiohttp
        except ImportError:
            logger.error("aiohttp is required for Slack alerts: pip install aiohttp")
            return

        color_map = {
            "critical": "danger",
            "high":     "danger",
            "medium":   "warning",
            "low":      "good",
            "info":     "#439FE0",
        }

        payload = {
            "attachments": [{
                "color":  color_map.get(alert["severity"], "warning"),
                "title":  alert["title"],
                "text":   alert["message"],
                "fields": [
                    {"title": "Severity", "value": alert["severity"],  "short": True},
                    {"title": "Type",     "value": alert["type"],      "short": True},
                    {"title": "Alert ID", "value": alert["id"],        "short": True},
                    {"title": "Time",     "value": alert["timestamp"], "short": True},
                ],
                "footer": "Roots Alert System",
                "ts": int(datetime.now(timezone.utc).timestamp()),
            }]
        }

        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(self.slack_webhook, json=payload, timeout=aiohttp.ClientTimeout(total=5))
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Slack alert rejected (%s): %s", resp.status, body)
        except Exception as exc:
            logger.error("Failed to send Slack alert: %s", exc)

    async def _send_pagerduty(self, alert: Dict[str, Any]) -> None:
        """Trigger a PagerDuty incident via the Events v2 API."""
        if not self.pagerduty_key:
            return

        try:
            import aiohttp
        except ImportError:
            logger.error("aiohttp is required for PagerDuty alerts: pip install aiohttp")
            return

        payload = {
            "routing_key":    self.pagerduty_key,
            "event_action":   "trigger",
            "dedup_key":      alert["id"],
            "payload": {
                "summary":    alert["title"],
                "source":     "roots-backend",
                "severity":   alert["severity"],   # PagerDuty accepts lowercase
                "timestamp":  alert["timestamp"],
                "component":  alert["type"],
                "custom_details": {
                    "message":  alert["message"],
                    "metadata": alert.get("metadata", {}),
                },
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5),
                )
                if resp.status not in (200, 202):
                    body = await resp.text()
                    logger.error("PagerDuty alert rejected (%s): %s", resp.status, body)
        except Exception as exc:
            logger.error("Failed to send PagerDuty alert: %s", exc)

    async def _send_email(self, alert: Dict[str, Any]) -> None:
        """Enqueue an email alert via the Celery worker."""
        if not self.email_recipients:
            return

        try:
            from app.workers.email_worker import send_email_alert
            send_email_alert.delay(alert, self.email_recipients)
        except Exception as exc:
            logger.error("Failed to enqueue email alert: %s", exc)

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    async def check_thresholds(self) -> None:
        """Run all threshold checks. Errors in one check never abort the others."""
        await asyncio.gather(
            self._check_database(),
            self._check_redis(),
            self._check_error_rate(),
            return_exceptions=True,
        )

    async def _check_database(self) -> None:
        # Imported lazily to avoid circular imports at module load time
        from app.db.session import db_manager

        try:
            db_status = await db_manager.health_check()
            if not db_status.get("write_engine"):
                await self.send_alert(
                    title="Database Connection Failed",
                    message="Cannot connect to the primary database",
                    severity=AlertSeverity.CRITICAL,
                    alert_type=AlertType.DATABASE,
                    metadata={"status": db_status},
                )
        except Exception as exc:
            logger.error("Database health check raised: %s", exc)

    async def _check_redis(self) -> None:
        from app.cache.redis_manager import redis_manager

        try:
            redis_status = await redis_manager.health_check()
            if not redis_status.get("connected"):
                await self.send_alert(
                    title="Redis Connection Failed",
                    message="Cannot connect to the Redis cache",
                    severity=AlertSeverity.HIGH,
                    alert_type=AlertType.REDIS,
                    metadata={"status": redis_status},
                )
        except Exception as exc:
            logger.error("Redis health check raised: %s", exc)

    async def _check_error_rate(self) -> None:
        try:
            error_rate = await self._get_error_rate()
            if error_rate > 0.10:
                await self.send_alert(
                    title="High API Error Rate",
                    message=f"Error rate is {error_rate * 100:.2f}% (threshold: 10%)",
                    severity=AlertSeverity.HIGH,
                    alert_type=AlertType.PERFORMANCE,
                    metadata={"error_rate": error_rate, "threshold": 0.10},
                )
        except Exception as exc:
            logger.error("Error-rate check raised: %s", exc)

    async def _get_error_rate(self) -> float:
        """
        Compute the API error rate from Redis counters written by middleware.

        Keys written by request middleware:
          metrics:requests:total   — total requests in the current window
          metrics:requests:errors  — 5xx responses in the current window

        Returns 0.0 if counters are unavailable (Redis down, cold start, etc.)
        """
        try:
            from app.cache.redis_manager import redis_manager

            total_raw  = await redis_manager.get("metrics:requests:total")
            errors_raw = await redis_manager.get("metrics:requests:errors")

            total  = int(total_raw)  if total_raw  else 0
            errors = int(errors_raw) if errors_raw else 0

            return (errors / total) if total > 0 else 0.0
        except Exception as exc:
            logger.warning("Could not retrieve error-rate metrics: %s", exc)
            return 0.0

    def get_recent_alerts(
        self,
        limit: int = 50,
        severity: Optional[AlertSeverity] = None,
        alert_type: Optional[AlertType] = None,
    ) -> List[Dict[str, Any]]:
        """Return recent in-memory alerts with optional filtering."""
        alerts = self.alerts[-limit:]
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity.value]
        if alert_type:
            alerts = [a for a in alerts if a["type"] == alert_type.value]
        return list(reversed(alerts))  # newest first


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

alert_manager = AlertManager()


# ---------------------------------------------------------------------------
# Background health monitor
# ---------------------------------------------------------------------------

async def system_health_monitor(interval_seconds: int = 60) -> None:
    """
    Long-running coroutine that polls system health on a fixed interval.
    Start with asyncio.create_task(system_health_monitor()) during app startup.
    """
    logger.info("System health monitor started (interval: %ds)", interval_seconds)
    while True:
        try:
            await alert_manager.check_thresholds()
        except Exception as exc:
            logger.error("Unexpected error in health monitor: %s", exc)
        await asyncio.sleep(interval_seconds)