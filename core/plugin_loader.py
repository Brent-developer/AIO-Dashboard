from __future__ import annotations

import importlib
import inspect
import re
from typing import Any

from core.base_driver import BiometricDriver


DRIVER_ALIASES = {"zk": "zkteco", "zk_tech": "zkteco", "hid_osdp": "osdp"}


def load_driver(manufacturer: str, host: str, port: int, **options: Any) -> BiometricDriver:
    slug = re.sub(r"[^a-z0-9_]", "", manufacturer.lower().replace("-", "_"))
    slug = DRIVER_ALIASES.get(slug, slug)
    module = importlib.import_module(f"drivers.{slug}")
    implementations = [
        cls
        for _, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, BiometricDriver) and cls is not BiometricDriver and cls.__module__ == module.__name__
    ]
    if len(implementations) != 1:
        raise RuntimeError(f"drivers.{slug} must expose exactly one BiometricDriver implementation")
    return implementations[0](host, port, **options)
