"""Settings resolved from environment variables.

``CLOUDKIT_MODE=local`` (default) points every adapter at the docker compose lab.
``CLOUDKIT_MODE=azure`` switches to real Azure resources authenticated with
``DefaultAzureCredential`` (az login locally, managed identity in Azure). No code changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum

# Well-known, publicly documented Azurite development account. Not a secret.
AZURITE_ACCOUNT = "devstoreaccount1"
AZURITE_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
)
# Well-known, publicly documented emulator SAS values. Not secrets.
EMULATOR_SAS_NAME = "RootManageSharedAccessKey"
EMULATOR_SAS_KEY = "SAS_KEY_VALUE"


class Mode(StrEnum):
    LOCAL = "local"
    AZURE = "azure"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    mode: Mode = Mode.LOCAL
    host: str = "localhost"

    # Azure resource names (used only in azure mode)
    storage_account: str = ""
    eventhubs_namespace: str = ""
    servicebus_namespace: str = ""
    key_vault_name: str = ""
    openai_endpoint: str = ""
    openai_api_version: str = "2024-10-21"
    appinsights_connection_string: str = ""

    # Local ports (overridable when something else already owns a port)
    blob_port: int = 10000
    eventhubs_port: int = 5672
    servicebus_port: int = 5673
    ollama_url: str = "http://localhost:11434/v1"
    otlp_endpoint: str = "http://localhost:4317"

    # Postgres is the same driver both ways; only the DSN changes
    pg_port: int = 5433
    postgres_dsn: str = "postgresql://lab:lab-local-only@localhost:5433/lab"

    extra: dict[str, str] = field(default_factory=dict)

    @property
    def is_local(self) -> bool:
        return self.mode is Mode.LOCAL

    @classmethod
    def from_env(cls) -> Settings:
        raw_mode = _env("CLOUDKIT_MODE", "local").lower()
        try:
            mode = Mode(raw_mode)
        except ValueError as exc:
            raise ValueError(f"CLOUDKIT_MODE must be 'local' or 'azure', got {raw_mode!r}") from exc
        host = _env("CLOUDKIT_LOCAL_HOST", "localhost")
        pg_port = int(_env("LAB_PG_PORT", "5433"))
        return cls(
            mode=mode,
            host=host,
            storage_account=_env("AZURE_STORAGE_ACCOUNT"),
            eventhubs_namespace=_env("AZURE_EVENTHUBS_NAMESPACE"),
            servicebus_namespace=_env("AZURE_SERVICEBUS_NAMESPACE"),
            key_vault_name=_env("AZURE_KEY_VAULT_NAME"),
            openai_endpoint=_env("AZURE_OPENAI_ENDPOINT"),
            openai_api_version=_env("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            appinsights_connection_string=_env("APPLICATIONINSIGHTS_CONNECTION_STRING"),
            blob_port=int(_env("CLOUDKIT_BLOB_PORT", "10000")),
            eventhubs_port=int(_env("CLOUDKIT_EVENTHUBS_PORT", "5672")),
            servicebus_port=int(_env("CLOUDKIT_SERVICEBUS_PORT", "5673")),
            ollama_url=_env("CLOUDKIT_OLLAMA_URL", f"http://{host}:11434/v1"),
            otlp_endpoint=_env("OTEL_EXPORTER_OTLP_ENDPOINT", f"http://{host}:4317"),
            pg_port=pg_port,
            postgres_dsn=_env(
                "POSTGRES_DSN", f"postgresql://lab:lab-local-only@{host}:{pg_port}/lab"
            ),
        )

    def require(self, *names: str) -> None:
        """Fail fast with a readable message when azure-mode settings are missing."""
        if self.is_local:
            return
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            env = ", ".join(_ENV_NAMES[n] for n in missing)
            raise RuntimeError(f"CLOUDKIT_MODE=azure but these env vars are unset: {env}")


_ENV_NAMES = {
    "storage_account": "AZURE_STORAGE_ACCOUNT",
    "eventhubs_namespace": "AZURE_EVENTHUBS_NAMESPACE",
    "servicebus_namespace": "AZURE_SERVICEBUS_NAMESPACE",
    "key_vault_name": "AZURE_KEY_VAULT_NAME",
    "openai_endpoint": "AZURE_OPENAI_ENDPOINT",
    "appinsights_connection_string": "APPLICATIONINSIGHTS_CONNECTION_STRING",
}
