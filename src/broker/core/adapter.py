from abc import ABC, abstractmethod

from src.broker.core.envelope import BrokerStats, TaskEnvelope, TaskMessage


class BrokerAdapter(ABC):
    @property
    @abstractmethod
    def backend_name(self) -> str: ...

    @abstractmethod
    async def publish(self, queue: str, envelope: TaskEnvelope) -> str: ...

    @abstractmethod
    async def consume(
        self, queue: str, worker_id: str, batch_size: int = 1
    ) -> list[TaskMessage]: ...

    @abstractmethod
    async def acknowledge(self, queue: str, message_id: str) -> None: ...

    @abstractmethod
    async def nack(self, queue: str, message_id: str, requeue: bool = True) -> None: ...

    @abstractmethod
    async def extend_lease(self, message_id: str, duration: int) -> None: ...

    @abstractmethod
    async def dead_letter(self, message_id: str, reason: str) -> None: ...

    @abstractmethod
    async def stats(self, queue: str) -> BrokerStats: ...

    async def health_check(self) -> bool:
        return True
