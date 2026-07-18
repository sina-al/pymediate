"""Stable application graph shared by every executable deployment."""

from dependency_injector import containers, providers
from opentelemetry import metrics, trace

from shop.application.behaviours.logger import LoggerBehavior
from shop.application.behaviours.metrics import MetricsBehavior
from shop.application.behaviours.tracing import TracingBehavior
from shop.application.customers.container import CustomersContainer
from shop.application.invoices.container import InvoicesContainer
from shop.application.mediator import create_mediator
from shop.application.orders.container import OrdersContainer
from shop.application.services.logger import StructlogLogger
from shop.application.statements.container import StatementsContainer
from shop.ports.orders.create_order import CreateOrderClock, ProductCatalogue
from shop.ports.statements.create_monthly_statement import StatementExchangeRates


class ApplicationContainer(containers.DeclarativeContainer):
    """Compose application feature modules around deployment-selected adapters."""

    __self__ = providers.Self()

    # Profile-selected outward adapters
    database: providers.Dependency[object] = providers.Dependency()
    unit: providers.Dependency[object] = providers.Dependency()
    catalogue = providers.Dependency(instance_of=ProductCatalogue)  # type: ignore[type-abstract]
    storage: providers.Dependency[object] = providers.Dependency()
    clock = providers.Dependency(instance_of=CreateOrderClock)  # type: ignore[type-abstract]
    inventory: providers.Dependency[object] = providers.Dependency()
    payments: providers.Dependency[object] = providers.Dependency()
    mailer: providers.Dependency[object] = providers.Dependency()
    rates = providers.Dependency(instance_of=StatementExchangeRates)  # type: ignore[type-abstract]
    renderer: providers.Dependency[object] = providers.Dependency()

    # Shared application services
    logger = providers.Singleton(StructlogLogger)
    tracer = providers.Singleton(trace.get_tracer, "shop.application")
    meter = providers.Singleton(metrics.get_meter, "shop.application")

    # Application-wide mediator behaviours
    logger_behavior = providers.Factory(LoggerBehavior, logger=logger)
    tracing_behavior = providers.Factory(TracingBehavior, tracer=tracer)
    metrics_behavior = providers.Factory(MetricsBehavior, meter=meter)

    # Application feature modules
    orders = providers.Container(
        OrdersContainer,
        catalogue=catalogue,
        clock=clock,
        create_inventory=inventory,
        create_payments=payments,
        confirmation_mailer=mailer,
        cancel_inventory=inventory,
        cancel_payments=payments,
        cancel_mailer=mailer,
        refund_payments=payments,
        refund_mailer=mailer,
        database=database,
        unit=unit,
        storage=storage,
        export_mailer=mailer,
        journal=database,
    )
    customers = providers.Container(
        CustomersContainer,
        database=database,
        unit=unit,
        journal=database,
    )
    invoices = providers.Container(
        InvoicesContainer,
        database=database,
        unit=unit,
        renderer=renderer,
        storage=storage,
        journal=database,
    )
    statements = providers.Container(
        StatementsContainer,
        database=database,
        unit=unit,
        rates=rates,
        renderer=renderer,
        storage=storage,
        journal=database,
    )
    # Mediator
    mediator = providers.Singleton(create_mediator, container=__self__)
