"""cloudkit — same code, local emulators or real Azure, selected by CLOUDKIT_MODE."""

from .clients import (
    blob_service,
    eventhub_consumer,
    eventhub_producer,
    kafka_config,
    llm_client,
    postgres_connect,
    servicebus_client,
)
from .config import Mode, Settings
from .secrets import SecretNotFound, get_secret

__all__ = [
    "Mode",
    "SecretNotFound",
    "Settings",
    "blob_service",
    "eventhub_consumer",
    "eventhub_producer",
    "get_secret",
    "kafka_config",
    "llm_client",
    "postgres_connect",
    "servicebus_client",
]
__version__ = "0.1.0"
