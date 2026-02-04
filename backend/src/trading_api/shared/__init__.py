"""Shared infrastructure - Module interface, registry, and plugins."""

from .client_factory import InterModuleClients
from .config import Settings, settings
from .datastore_interface import (
    DatastoreInterface,
    TableInterface,
    TimeSeriesTableInterface,
    create_dynamic_table_model,
)
from .datastore_registry import DatastoreRegistry
from .module_interface import Module, ModuleApp
from .module_registry import ModuleRegistry
from .provider_interface import Provider
from .provider_registry import ProviderRegistry
from .ws import FastWSAdapter

__all__ = [
    "Module",
    "ModuleApp",
    "ModuleRegistry",
    "Provider",
    "ProviderRegistry",
    "DatastoreRegistry",
    "create_dynamic_table_model",
    "FastWSAdapter",
    "settings",
    "Settings",
    "InterModuleClients",
    "DatastoreInterface",
    "TableInterface",
    "TimeSeriesTableInterface",
]
