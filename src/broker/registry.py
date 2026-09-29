from src.broker.core.adapter import BrokerAdapter
from src.broker.native.adapter import NativeBrokerAdapter

_broker_registry: dict[str, BrokerAdapter] = {"native": NativeBrokerAdapter()}


def get_broker_adapter(backend_name: str = "native") -> BrokerAdapter:
    adapter = _broker_registry.get(backend_name.lower())
    if adapter is None:
        raise ValueError(
            f"Unsupported broker backend '{backend_name}'. Registered backends: {list(_broker_registry.keys())}"
        )
    return adapter


def register_broker_adapter(adapter: BrokerAdapter) -> None:
    _broker_registry[adapter.backend_name.lower()] = adapter


def list_registered_backends() -> list[str]:
    return list(_broker_registry.keys())


class BrokerRegistry:
    get = staticmethod(get_broker_adapter)
    register = staticmethod(register_broker_adapter)
    list_backends = staticmethod(list_registered_backends)
