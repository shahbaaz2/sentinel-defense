"""Repository/provider protocols (blueprint §6.1).

Business logic in services/* and ai/* depends on these Protocols, never on a vendor SDK directly.
This is what lets Postgres be complemented by OpenSearch later, and MLX be replaced by a GPU
endpoint later, without touching the incident engine, policy engine, or dashboard contracts.

Concrete implementations are added phase by phase; this file only grows the *interface* surface as
each phase actually needs it, rather than being speculatively filled in now.
"""

from typing import Protocol

from domain.models.events import NormalizedEvent


class EventRepository(Protocol):
    async def save(self, event: NormalizedEvent) -> None: ...

    async def get(self, event_id: str) -> NormalizedEvent | None: ...
