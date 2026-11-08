"""Client factories. Each returns the *official* Azure SDK client (or OpenAI client),
configured for the emulator in local mode and for Entra ID auth in azure mode.

Application code depends only on these factories, so the switch to the cloud is an
environment-variable change, never a code change.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from .config import (
    AZURITE_ACCOUNT,
    AZURITE_KEY,
    EMULATOR_SAS_KEY,
    EMULATOR_SAS_NAME,
    Settings,
)

if TYPE_CHECKING:
    from azure.eventhub import EventHubConsumerClient, EventHubProducerClient
    from azure.servicebus import ServiceBusClient
    from azure.storage.blob import BlobServiceClient
    from openai import OpenAI


@lru_cache(maxsize=1)
def credential() -> Any:
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


# ---------------------------------------------------------------- storage ---
def blob_connection_string(s: Settings) -> str:
    return (
        "DefaultEndpointsProtocol=http;"
        f"AccountName={AZURITE_ACCOUNT};AccountKey={AZURITE_KEY};"
        f"BlobEndpoint=http://{s.host}:{s.blob_port}/{AZURITE_ACCOUNT};"
    )


def blob_service(s: Settings | None = None) -> BlobServiceClient:
    from azure.storage.blob import BlobServiceClient

    s = s or Settings.from_env()
    if s.is_local:
        return BlobServiceClient.from_connection_string(blob_connection_string(s))
    s.require("storage_account")
    url = f"https://{s.storage_account}.blob.core.windows.net"
    return BlobServiceClient(account_url=url, credential=credential())


# ------------------------------------------------------------- event hubs ---
def eventhubs_connection_string(s: Settings) -> str:
    return (
        f"Endpoint=sb://{s.host}:{s.eventhubs_port};"
        f"SharedAccessKeyName={EMULATOR_SAS_NAME};SharedAccessKey={EMULATOR_SAS_KEY};"
        "UseDevelopmentEmulator=true;"
    )


def eventhub_producer(hub: str, s: Settings | None = None) -> EventHubProducerClient:
    from azure.eventhub import EventHubProducerClient

    s = s or Settings.from_env()
    if s.is_local:
        return EventHubProducerClient.from_connection_string(
            eventhubs_connection_string(s), eventhub_name=hub
        )
    s.require("eventhubs_namespace")
    return EventHubProducerClient(
        fully_qualified_namespace=f"{s.eventhubs_namespace}.servicebus.windows.net",
        eventhub_name=hub,
        credential=credential(),
    )


def eventhub_consumer(
    hub: str, consumer_group: str = "$Default", s: Settings | None = None
) -> EventHubConsumerClient:
    from azure.eventhub import EventHubConsumerClient

    s = s or Settings.from_env()
    if s.is_local:
        return EventHubConsumerClient.from_connection_string(
            eventhubs_connection_string(s), consumer_group=consumer_group, eventhub_name=hub
        )
    s.require("eventhubs_namespace")
    return EventHubConsumerClient(
        fully_qualified_namespace=f"{s.eventhubs_namespace}.servicebus.windows.net",
        eventhub_name=hub,
        consumer_group=consumer_group,
        credential=credential(),
    )


def kafka_config(s: Settings | None = None) -> dict[str, str]:
    """librdkafka/confluent-kafka settings for the Event Hubs Kafka endpoint."""
    s = s or Settings.from_env()
    if s.is_local:
        return {
            "bootstrap.servers": f"{s.host}:9092",
            "security.protocol": "SASL_PLAINTEXT",
            "sasl.mechanism": "PLAIN",
            "sasl.username": "$ConnectionString",
            "sasl.password": eventhubs_connection_string(s),
        }
    s.require("eventhubs_namespace")
    return {
        "bootstrap.servers": f"{s.eventhubs_namespace}.servicebus.windows.net:9093",
        "security.protocol": "SASL_SSL",
        "sasl.mechanism": "OAUTHBEARER",  # pair with an Entra ID token callback
    }


# ------------------------------------------------------------ service bus ---
def servicebus_client(s: Settings | None = None) -> ServiceBusClient:
    from azure.servicebus import ServiceBusClient

    s = s or Settings.from_env()
    if s.is_local:
        conn = (
            f"Endpoint=sb://{s.host}:{s.servicebus_port};"
            f"SharedAccessKeyName={EMULATOR_SAS_NAME};SharedAccessKey={EMULATOR_SAS_KEY};"
            "UseDevelopmentEmulator=true;"
        )
        return ServiceBusClient.from_connection_string(conn)
    s.require("servicebus_namespace")
    return ServiceBusClient(
        fully_qualified_namespace=f"{s.servicebus_namespace}.servicebus.windows.net",
        credential=credential(),
    )


# -------------------------------------------------------------------- llm ---
def llm_client(s: Settings | None = None) -> OpenAI:
    """OpenAI-compatible client: Ollama locally, Azure OpenAI (Entra ID auth) in the cloud."""
    s = s or Settings.from_env()
    if s.is_local:
        from openai import OpenAI

        return OpenAI(base_url=s.ollama_url, api_key="ollama")  # Ollama ignores the key
    s.require("openai_endpoint")
    from azure.identity import get_bearer_token_provider
    from openai import AzureOpenAI

    token = get_bearer_token_provider(credential(), "https://cognitiveservices.azure.com/.default")
    return AzureOpenAI(
        azure_endpoint=s.openai_endpoint,
        azure_ad_token_provider=token,
        api_version=s.openai_api_version,
    )


# --------------------------------------------------------------- postgres ---
def postgres_connect(s: Settings | None = None) -> Any:
    """psycopg connection. In Azure, put the DSN (or an Entra token flow) in Key Vault."""
    import psycopg

    s = s or Settings.from_env()
    return psycopg.connect(s.postgres_dsn)
