"""Azure secondary adapters for Shop."""

from shop.adapters.azure.queue import AzureServiceBusMessageBroker
from shop.adapters.azure.storage import AzureBlobStorage

__all__ = ["AzureBlobStorage", "AzureServiceBusMessageBroker"]
