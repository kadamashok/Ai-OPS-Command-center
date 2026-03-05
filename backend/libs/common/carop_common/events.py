import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer

from .config import settings

logger = logging.getLogger(__name__)


class KafkaEventPublisher:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        try:
            self._producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap)
            await self._producer.start()
            self._started = True
        except Exception as exc:  # nosec B110
            logger.warning("Kafka unavailable at startup: %s", exc)
            self._producer = None
            self._started = False

    async def stop(self) -> None:
        if not self._producer:
            return
        try:
            await self._producer.stop()
        except Exception as exc:  # nosec B110
            logger.warning("Kafka stop failed: %s", exc)
        finally:
            self._producer = None
            self._started = False

    async def publish(self, topic: str, payload: dict[str, Any]) -> bool:
        if not self._started or not self._producer:
            return False
        try:
            await self._producer.send_and_wait(topic, json.dumps(payload).encode("utf-8"))
            return True
        except Exception as exc:  # nosec B110
            logger.warning("Kafka publish failed topic=%s err=%s", topic, exc)
            return False
