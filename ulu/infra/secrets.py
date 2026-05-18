"""Secret management abstraction supporting env, HashiCorp Vault, and AWS Secrets Manager.

Item 110 from production roadmap.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from ulu.infra.logging import logger


class SecretManager(ABC):
    """Abstract secret manager for production-grade secret retrieval."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Retrieves secret by key."""

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """Stores secret by key."""


class EnvSecretManager(SecretManager):
    """Reads secrets from environment variables. Default for development."""

    def get(self, key: str) -> str | None:
        return os.environ.get(key)

    def set(self, key: str, value: str) -> None:
        os.environ[key] = value
        logger.info("secret_set_env", key=key)


class VaultSecretManager(SecretManager):
    """HashiCorp Vault integration (stub — requires hvac in production)."""

    def __init__(self, vault_addr: str = "", token: str = "", mount_point: str = "secret") -> None:
        self.vault_addr = vault_addr
        self.token = token
        self.mount_point = mount_point
        self._cache: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        if key in self._cache:
            return self._cache[key]
        logger.warning("vault_secret_read_stub", key=key, vault_addr=self.vault_addr)
        return None

    def set(self, key: str, value: str) -> None:
        self._cache[key] = value
        logger.info("vault_secret_write_stub", key=key, vault_addr=self.vault_addr)


class AwsSecretsManager(SecretManager):
    """AWS Secrets Manager integration (stub — requires boto3 in production)."""

    def __init__(self, region: str = "ap-south-1") -> None:
        self.region = region
        self._cache: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        if key in self._cache:
            return self._cache[key]
        logger.warning("aws_secret_read_stub", key=key, region=self.region)
        return None

    def set(self, key: str, value: str) -> None:
        self._cache[key] = value
        logger.info("aws_secret_write_stub", key=key, region=self.region)


class CompositeSecretManager(SecretManager):
    """Tries backends in order until a secret is found."""

    def __init__(self, backends: list[SecretManager]) -> None:
        self.backends = backends

    def get(self, key: str) -> str | None:
        for backend in self.backends:
            value = backend.get(key)
            if value is not None:
                return value
        return None

    def set(self, key: str, value: str) -> None:
        if self.backends:
            self.backends[0].set(key, value)
