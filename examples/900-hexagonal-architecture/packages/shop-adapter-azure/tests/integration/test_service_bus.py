"""Exercise the Service Bus adapter against Microsoft's containerized emulator."""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

import pytest
from azure.servicebus import ServiceBusSubQueue
from azure.servicebus.aio import ServiceBusClient
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.waiting_utils import wait_for_logs

from shop.adapters.azure import AzureServiceBusMessageBroker
from shop.ports.integration import IntegrationMessage, deserialize_message
from shop.ports.outbox import OutboxMessage


class CountedDelivery(Protocol):
    """Expose the Service Bus delivery count asserted by this adapter test."""

    delivery_count: int


@pytest.mark.containers
async def test_service_bus_renew_redeliver_and_move_poison_message_to_dlq() -> None:
    # Arrange
    if os.environ.get("RUN_AZURE_SERVICE_BUS_TESTCONTAINERS") != "1":
        pytest.skip("set RUN_AZURE_SERVICE_BUS_TESTCONTAINERS=1 to run the Service Bus emulator")

    # Act
    password = "ShopExample-Strong-Password-123!"
    config = Path(__file__).with_name("service-bus-config.json").resolve()
    with Network() as network:
        sql = DockerContainer(
            "mcr.microsoft.com/mssql/server:2022-latest",
            network=network,
            network_aliases=["sqlserver"],
        ).with_envs(ACCEPT_EULA="Y", MSSQL_SA_PASSWORD=password)
        with sql:
            emulator = (
                DockerContainer(
                    "mcr.microsoft.com/azure-messaging/servicebus-emulator:latest",
                    network=network,
                    network_aliases=["servicebus-emulator"],
                )
                .with_envs(
                    ACCEPT_EULA="Y",
                    SQL_SERVER="sqlserver",
                    MSSQL_SA_PASSWORD=password,
                )
                .with_volume_mapping(
                    str(config), "/ServiceBus_Emulator/ConfigFiles/Config.json", "ro"
                )
                .with_exposed_ports(5672)
            )
            with emulator:
                wait_for_logs(emulator, "Emulator Service is Successfully Up", timeout=120)
                host = emulator.get_container_host_ip()
                port = emulator.get_exposed_port(5672)
                connection_string = (
                    f"Endpoint=sb://{host}:{port};"
                    "SharedAccessKeyName=RootManageSharedAccessKey;"
                    "SharedAccessKey=SAS_KEY_VALUE;UseDevelopmentEmulator=true;"
                )
                adapter = AzureServiceBusMessageBroker(
                    "shop-events", connection_string=connection_string, wait_seconds=1
                )
                message = IntegrationMessage(
                    "12345678-1234-5678-1234-567812345678",
                    "example.Event",
                    1,
                    datetime(2026, 7, 15, tzinfo=UTC),
                    {},
                )

                await adapter.publish(OutboxMessage(message, {}))
                first = await adapter.receive()
                assert first is not None
                await first.renew()
                await first.abandon()

                delivery_counts: list[int] = []
                for _ in range(4):
                    delivery = await adapter.receive()
                    assert delivery is not None
                    delivery_counts.append(cast("CountedDelivery", delivery).delivery_count)
                    await delivery.abandon()

                source_after_threshold = await adapter.receive()
                async with ServiceBusClient.from_connection_string(
                    connection_string
                ) as dead_letter_client:
                    async with dead_letter_client.get_queue_receiver(
                        "shop-events",
                        sub_queue=ServiceBusSubQueue.DEAD_LETTER,
                        max_wait_time=5,
                    ) as dead_letter_receiver:
                        dead_letters = await dead_letter_receiver.receive_messages(
                            max_message_count=1,
                            max_wait_time=5,
                        )
                        assert dead_letters
                        dead_letter_message = deserialize_message(
                            b"".join(bytes(section) for section in dead_letters[0].body).decode()
                        )
                        await dead_letter_receiver.complete_message(dead_letters[0])
                        dead_letters_after_completion = await dead_letter_receiver.receive_messages(
                            max_message_count=1,
                            max_wait_time=1,
                        )
                await adapter.close()

                # Assert
                assert first.message == message
                assert delivery_counts == [2, 3, 4, 5]
                assert source_after_threshold is None
                assert dead_letter_message == message
                assert dead_letters_after_completion == []
