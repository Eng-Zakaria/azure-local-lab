"""Secret lookup: environment variables locally, Azure Key Vault in the cloud.

Key Vault secret names allow only letters, digits and dashes, so ``get_secret("db-password")``
reads Key Vault secret ``db-password`` in azure mode and env var ``DB_PASSWORD`` locally.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from .config import Settings


class SecretNotFound(KeyError):
    pass


def env_name(secret_name: str) -> str:
    return secret_name.replace("-", "_").upper()


@lru_cache(maxsize=4)
def _vault_client(vault_name: str) -> Any:
    from azure.keyvault.secrets import SecretClient

    from .clients import credential

    return SecretClient(vault_url=f"https://{vault_name}.vault.azure.net", credential=credential())


def get_secret(name: str, default: str | None = None, s: Settings | None = None) -> str:
    s = s or Settings.from_env()
    if s.is_local:
        value = os.environ.get(env_name(name), default)
    else:
        s.require("key_vault_name")
        from azure.core.exceptions import ResourceNotFoundError

        try:
            value = _vault_client(s.key_vault_name).get_secret(name).value
        except ResourceNotFoundError:
            value = default
    if value is None:
        where = f"env var {env_name(name)}" if s.is_local else f"Key Vault {s.key_vault_name}"
        raise SecretNotFound(f"secret {name!r} not found in {where}")
    return value
