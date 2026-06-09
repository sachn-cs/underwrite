"""Generic store-backed repository for nano-service state persistence.

Replaces the manual ``__sync_store`` / ``__load_store`` boilerplate
with a reusable, type-safe abstraction.  Encapsulates key management,
serialization, and type validation in one place.

Usage::

    from underwrite.services.persistence import StoreRepository

    class MyService(NanoService):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._data: dict[str, Any] = {}
            self._repo = StoreRepository[dict](self.store, f"{self.service_id}:data")
            self._loaded = self._repo.load(default={})
            if self._loaded is not None:
                self._data = self._loaded

        def _sync(self) -> None:
            self._repo.save(self._data)
"""

from __future__ import annotations

import threading
from typing import Any, Generic, TypeVar, cast

from underwrite.__logger__ import logger
from underwrite.__store__ import Store

T = TypeVar("T")


class StoreRepository(Generic[T]):
    """Generic thread-safe repository for store-backed state.

    Handles key prefixing, serialization, and type-safe loading.
    Does **not** manage its own lock — the caller is responsible for
    concurrency control (use the service's own lock).
    """

    def __init__(self, store: Store, key: str) -> None:
        """Initialise the repository.

        Args:
            store: The shared Store backend.
            key: Store key to read/write state under.
        """
        self._store = store
        self._key = key

    def load(self, default: T | None = None) -> T | None:
        """Load state from the store.

        Args:
            default: Value returned when the key is missing.

        Returns:
            The deserialized state, or *default* if the key does not
            exist or the read fails.
        """
        try:
            raw = self._store.get(self._key)
            if raw is None:
                return default
            return self.deserialize(raw)
        except Exception:
            logger.exception("failed to load %s from store", self._key)
            return default

    def save(self, data: T) -> None:
        """Persist state to the store.

        Args:
            data: The state to persist.

        Raises:
            StoreError: If the store write fails.
        """
        self._store.set(self._key, self.serialize(data))

    def deserialize(self, raw: Any) -> T:
        """Override in subclasses for custom deserialization."""
        return cast(T, raw)

    def serialize(self, data: T) -> Any:
        """Override in subclasses for custom serialization."""
        return data


class TypedStoreRepository(StoreRepository[T]):
    """A ``StoreRepository`` that validates the loaded value type.

    If the stored value is not an instance of *expected_type* the
    repository returns *default*, preventing silent data corruption.
    """

    def __init__(
        self,
        store: Store,
        key: str,
        expected_type: type | tuple[type, ...],
    ) -> None:
        super().__init__(store, key)
        self._expected_type = expected_type

    def load(self, default: T | None = None) -> T | None:
        raw = super().load(default)
        if raw is default or raw is None:
            return default
        if not isinstance(raw, self._expected_type):
            logger.warning(
                "expected %s for key %s, got %s — returning default",
                self._expected_type,
                self._key,
                type(raw).__name__,
            )
            return default
        return raw


class BatchedStoreRepository(TypedStoreRepository[T]):
    """A ``TypedStoreRepository`` with batched persistence.

    Instead of writing to the store on every ``save()`` call, accumulates
    a counter and only triggers the actual sync every *sync_interval*
    ``incr_and_maybe_sync()`` calls.  Useful for high-frequency state
    updates where O(n) serialization is a concern.

    Subclasses must call ``incr_and_maybe_sync()`` or ``force_sync()``
    to persist; a plain ``save()`` still writes immediately.
    """

    def __init__(
        self,
        store: Store,
        key: str,
        expected_type: type | tuple[type, ...],
        sync_interval: int = 10,
    ) -> None:
        super().__init__(store, key, expected_type)
        self.__batch_lock: threading.Lock = threading.Lock()
        self.__sync_interval: int = max(sync_interval, 1)
        self.__sync_counter: int = 0

    def incr_and_maybe_sync(self, data: T) -> bool:
        """Increments the counter and triggers sync if threshold reached.

        Args:
            data: The state to persist when the threshold is met.

        Returns:
            True if a sync was triggered, False otherwise.
        """
        with self.__batch_lock:
            self.__sync_counter += 1
            if self.__sync_counter >= self.__sync_interval:
                self.__sync_counter = 0
                self.save(data)
                return True
        return False

    def force_sync(self, data: T) -> None:
        """Immediately persists regardless of the counter."""
        with self.__batch_lock:
            self.__sync_counter = 0
            self.save(data)

    def reset_counter(self) -> None:
        """Resets the internal sync counter without persisting."""
        with self.__batch_lock:
            self.__sync_counter = 0
