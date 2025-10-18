"""Tests for DependencyInjectorResolver."""

from dataclasses import dataclass

from dependency_injector import containers, providers

from pymediate import DependencyInjectorResolver, Handler, Mediator, Request

# Define test domain objects


@dataclass
class EmailSentResponse:
    """Response indicating email was sent."""

    success: bool
    message_id: str


class SendEmailRequest(Request[EmailSentResponse]):
    """Request to send an email."""

    def __init__(self, to: str, subject: str, body: str):
        self.to = to
        self.subject = subject
        self.body = body


# Mock email service for testing


class EmailService:
    """Mock email service."""

    def __init__(self, smtp_host: str, smtp_port: int):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sent_emails: list[dict] = []

    def send(self, to: str, subject: str, body: str) -> str:
        """Send an email and return message ID."""
        message_id = f"msg-{len(self.sent_emails) + 1}"
        self.sent_emails.append({"to": to, "subject": subject, "body": body, "id": message_id})
        return message_id


# Handler with dependency injection


class SendEmailHandler(Handler[SendEmailRequest]):
    """Handler that sends emails using injected EmailService."""

    def __init__(self, email_service: EmailService):
        self.email_service = email_service

    def __call__(self, request: SendEmailRequest) -> EmailSentResponse:
        message_id = self.email_service.send(request.to, request.subject, request.body)
        return EmailSentResponse(success=True, message_id=message_id)


# Container configuration


class ApplicationContainer(containers.DeclarativeContainer):
    """DI container for the application."""

    # Configuration
    config = providers.Configuration()

    # Email service
    email_service = providers.Singleton(
        EmailService, smtp_host=config.smtp.host, smtp_port=config.smtp.port
    )

    # Handler with injected email service
    send_email_handler = providers.Factory(SendEmailHandler, email_service=email_service)

    # Self-reference for resolver
    __self__ = providers.Self()

    # Mediator
    mediator: providers.Singleton[Mediator] = providers.Singleton(
        Mediator, resolver=providers.Singleton(DependencyInjectorResolver, container=__self__)
    )


def test_di_resolver_basic():
    """Test basic DI resolver functionality."""
    container = ApplicationContainer()
    container.config.smtp.host.from_value("smtp.example.com")
    container.config.smtp.port.from_value(587)

    resolver = container.mediator()._resolver
    handler = resolver.resolve(SendEmailRequest)

    assert isinstance(handler, SendEmailHandler)
    assert handler.email_service.smtp_host == "smtp.example.com"
    assert handler.email_service.smtp_port == 587


def test_di_resolver_with_mediator():
    """Test using DI resolver with mediator."""
    container = ApplicationContainer()
    container.config.smtp.host.from_value("smtp.test.com")
    container.config.smtp.port.from_value(25)

    mediator = container.mediator()

    request = SendEmailRequest(to="user@example.com", subject="Test Email", body="This is a test")
    response = mediator.send(request)

    assert response.success is True
    assert response.message_id == "msg-1"

    # Verify email was sent through the service
    email_service = container.email_service()
    assert len(email_service.sent_emails) == 1
    assert email_service.sent_emails[0]["to"] == "user@example.com"
    assert email_service.sent_emails[0]["subject"] == "Test Email"


def test_di_resolver_singleton_behavior():
    """Test that handler instances are managed by the container."""
    container = ApplicationContainer()
    container.config.smtp.host.from_value("smtp.example.com")
    container.config.smtp.port.from_value(587)

    mediator = container.mediator()

    # Send multiple emails
    request1 = SendEmailRequest(to="user1@example.com", subject="Email 1", body="Body 1")
    request2 = SendEmailRequest(to="user2@example.com", subject="Email 2", body="Body 2")

    response1 = mediator.send(request1)
    response2 = mediator.send(request2)

    assert response1.message_id == "msg-1"
    assert response2.message_id == "msg-2"

    # Verify both emails went through same service instance
    email_service = container.email_service()
    assert len(email_service.sent_emails) == 2


def test_di_resolver_handler_not_found():
    """Test error when handler provider is not in container."""

    class UnregisteredResponse:
        pass

    class UnregisteredRequest(Request[UnregisteredResponse]):
        pass

    container = ApplicationContainer()
    resolver = DependencyInjectorResolver(container)

    try:
        resolver.resolve(UnregisteredRequest)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        # New implementation uses type inspection, not naming conventions
        assert "No handler found" in str(e)
        assert "UnregisteredRequest" in str(e)


# Test with multiple handlers


@dataclass
class NotificationSentResponse:
    """Response for notification."""

    sent: bool
    channel: str


class SendNotificationRequest(Request[NotificationSentResponse]):
    """Request to send a notification."""

    def __init__(self, user_id: int, message: str):
        self.user_id = user_id
        self.message = message


class NotificationService:
    """Mock notification service."""

    def __init__(self):
        self.notifications = []

    def send(self, user_id: int, message: str):
        self.notifications.append({"user_id": user_id, "message": message})


class SendNotificationHandler(Handler[SendNotificationRequest]):
    """Handler for sending notifications."""

    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service

    def __call__(self, request: SendNotificationRequest) -> NotificationSentResponse:
        self.notification_service.send(request.user_id, request.message)
        return NotificationSentResponse(sent=True, channel="push")


class MultiHandlerContainer(containers.DeclarativeContainer):
    """Container with multiple handlers."""

    # Services
    email_service = providers.Singleton(EmailService, smtp_host="localhost", smtp_port=25)
    notification_service = providers.Singleton(NotificationService)

    # Handlers
    send_email_handler = providers.Factory(SendEmailHandler, email_service=email_service)
    send_notification_handler = providers.Factory(
        SendNotificationHandler, notification_service=notification_service
    )

    # Mediator
    __self__ = providers.Self()
    mediator: providers.Singleton[Mediator] = providers.Singleton(
        Mediator, resolver=providers.Singleton(DependencyInjectorResolver, container=__self__)
    )


def test_multiple_handlers_with_di():
    """Test multiple different handlers in same container."""
    container = MultiHandlerContainer()
    mediator = container.mediator()

    # Send email
    email_request = SendEmailRequest(to="test@example.com", subject="Hi", body="Hello")
    email_response = mediator.send(email_request)
    assert email_response.success is True

    # Send notification
    notif_request = SendNotificationRequest(user_id=123, message="Welcome!")
    notif_response = mediator.send(notif_request)
    assert notif_response.sent is True
    assert notif_response.channel == "push"

    # Verify both were sent
    assert len(container.email_service().sent_emails) == 1
    assert len(container.notification_service().notifications) == 1


def test_di_resolver_type_inspection():
    """Test that DI resolver uses type inspection, not naming conventions."""
    container = ApplicationContainer()
    container.config.smtp.host.from_value("smtp.example.com")
    container.config.smtp.port.from_value(587)

    resolver = DependencyInjectorResolver(container)

    # Resolver should have found SendEmailRequest by inspecting handler types
    assert SendEmailRequest in resolver._handler_providers

    # Verify we can resolve it
    handler = resolver.resolve(SendEmailRequest)
    assert isinstance(handler, SendEmailHandler)
