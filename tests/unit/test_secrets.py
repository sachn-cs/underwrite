"""Unit tests for secret management backends."""

from __future__ import annotations

import os

from ulu.infra.secrets import (
    AwsSecretsManager,
    CompositeSecretManager,
    EnvSecretManager,
    VaultSecretManager,
)


class TestEnvSecretManager:
    def test_get_existing(self) -> None:
        os.environ["TEST_KEY"] = "test_value"
        mgr = EnvSecretManager()
        assert mgr.get("TEST_KEY") == "test_value"

    def test_get_missing(self) -> None:
        mgr = EnvSecretManager()
        assert mgr.get("NONEXISTENT_KEY_12345") is None

    def test_set(self) -> None:
        mgr = EnvSecretManager()
        mgr.set("TEST_KEY2", "test_value2")
        assert os.environ.get("TEST_KEY2") == "test_value2"


class TestVaultSecretManager:
    def test_get_returns_none(self) -> None:
        mgr = VaultSecretManager(vault_addr="http://vault:8200", token="token")
        assert mgr.get("secret") is None

    def test_set_and_get_cached(self) -> None:
        mgr = VaultSecretManager()
        mgr.set("secret", "value")
        assert mgr.get("secret") == "value"


class TestAwsSecretsManager:
    def test_get_returns_none(self) -> None:
        mgr = AwsSecretsManager(region="ap-south-1")
        assert mgr.get("secret") is None

    def test_set_and_get_cached(self) -> None:
        mgr = AwsSecretsManager()
        mgr.set("secret", "value")
        assert mgr.get("secret") == "value"


class TestCompositeSecretManager:
    def test_falls_back(self) -> None:
        env = EnvSecretManager()
        vault = VaultSecretManager()
        vault.set("fallback_key", "fallback_value")
        composite = CompositeSecretManager([env, vault])
        assert composite.get("fallback_key") == "fallback_value"

    def test_prefers_first_backend(self) -> None:
        env = EnvSecretManager()
        env.set("priority_key", "env_value")
        vault = VaultSecretManager()
        vault.set("priority_key", "vault_value")
        composite = CompositeSecretManager([env, vault])
        assert composite.get("priority_key") == "env_value"

    def test_set_writes_to_first(self) -> None:
        env = EnvSecretManager()
        vault = VaultSecretManager()
        composite = CompositeSecretManager([env, vault])
        composite.set("new_key", "new_value")
        assert env.get("new_key") == "new_value"
        assert vault.get("new_key") is None

    def test_no_backends(self) -> None:
        composite = CompositeSecretManager([])
        assert composite.get("key") is None
