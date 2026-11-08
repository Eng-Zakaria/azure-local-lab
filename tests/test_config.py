import pytest

from cloudkit import Mode, SecretNotFound, Settings, get_secret
from cloudkit.clients import (
    blob_connection_string,
    blob_service,
    eventhubs_connection_string,
    kafka_config,
    llm_client,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in [
        "CLOUDKIT_MODE",
        "CLOUDKIT_LOCAL_HOST",
        "AZURE_STORAGE_ACCOUNT",
        "AZURE_EVENTHUBS_NAMESPACE",
        "AZURE_KEY_VAULT_NAME",
        "AZURE_OPENAI_ENDPOINT",
        "POSTGRES_DSN",
    ]:
        monkeypatch.delenv(k, raising=False)


def test_default_mode_is_local():
    s = Settings.from_env()
    assert s.mode is Mode.LOCAL and s.is_local


def test_invalid_mode_rejected(monkeypatch):
    monkeypatch.setenv("CLOUDKIT_MODE", "aws")
    with pytest.raises(ValueError, match="local' or 'azure"):
        Settings.from_env()


def test_local_host_override_flows_everywhere(monkeypatch):
    monkeypatch.setenv("CLOUDKIT_LOCAL_HOST", "lab")
    s = Settings.from_env()
    assert "http://lab:10000/devstoreaccount1" in blob_connection_string(s)
    assert "sb://lab:5672" in eventhubs_connection_string(s)
    assert s.ollama_url == "http://lab:11434/v1"
    assert "@lab:5433" in s.postgres_dsn


def test_local_blob_client_targets_azurite():
    client = blob_service(Settings.from_env())
    assert client.account_name == "devstoreaccount1"
    assert client.url.startswith("http://localhost:10000/")


def test_azure_mode_fails_fast_with_env_var_names(monkeypatch):
    monkeypatch.setenv("CLOUDKIT_MODE", "azure")
    with pytest.raises(RuntimeError, match="AZURE_STORAGE_ACCOUNT"):
        blob_service(Settings.from_env())


def test_azure_blob_client_uses_account_url(monkeypatch):
    monkeypatch.setenv("CLOUDKIT_MODE", "azure")
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT", "stlabdemo")
    client = blob_service(Settings.from_env())
    assert client.url.startswith("https://stlabdemo.blob.core.windows.net")


def test_kafka_config_switches_protocol(monkeypatch):
    local = kafka_config(Settings.from_env())
    assert local["bootstrap.servers"] == "localhost:9092"
    assert local["security.protocol"] == "SASL_PLAINTEXT"
    monkeypatch.setenv("CLOUDKIT_MODE", "azure")
    monkeypatch.setenv("AZURE_EVENTHUBS_NAMESPACE", "evh-lab")
    cloud = kafka_config(Settings.from_env())
    assert cloud["bootstrap.servers"] == "evh-lab.servicebus.windows.net:9093"
    assert cloud["security.protocol"] == "SASL_SSL"


def test_local_llm_client_points_at_ollama():
    client = llm_client(Settings.from_env())
    assert str(client.base_url).startswith("http://localhost:11434/v1")


def test_secret_from_env_locally(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "s3cret")
    assert get_secret("db-password") == "s3cret"


def test_missing_secret_raises_with_location():
    with pytest.raises(SecretNotFound, match="DOES_NOT_EXIST"):
        get_secret("does-not-exist")


def test_secret_default_used():
    assert get_secret("does-not-exist", default="x") == "x"
