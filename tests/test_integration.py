"""Integration tests for the complete mediator pattern workflow."""

import pytest

from pymediate import Handler, Mediator, Request, ResponseTypeMismatchError, SimpleResolver


def test_complete_workflow():
    """Test complete workflow from request definition to response."""

    # Define domain objects
    class UserCreatedResponse:
        def __init__(self, user_id: int, username: str):
            self.user_id = user_id
            self.username = username

    class CreateUserRequest(Request[UserCreatedResponse]):
        def __init__(self, username: str, email: str):
            self.username = username
            self.email = email

    # Define handler
    class CreateUserHandler(Handler[CreateUserRequest]):
        def __init__(self):
            self.next_id = 1

        def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
            user_id = self.next_id
            self.next_id += 1
            return UserCreatedResponse(user_id, request.username)

    # Set up mediator
    resolver = SimpleResolver()
    resolver.register(CreateUserRequest, CreateUserHandler())
    mediator = Mediator(resolver)

    # Execute request
    request = CreateUserRequest("alice", "alice@example.com")
    response = mediator.send(request)

    # Verify
    assert response.user_id == 1
    assert response.username == "alice"


def test_multiple_request_types_workflow():
    """Test workflow with multiple different request types."""

    # User management
    class UserResponse:
        def __init__(self, user_id: int, name: str):
            self.user_id = user_id
            self.name = name

    class GetUserRequest(Request[UserResponse]):
        def __init__(self, user_id: int):
            self.user_id = user_id

    class GetUserHandler(Handler[GetUserRequest]):
        def __call__(self, request: GetUserRequest) -> UserResponse:
            # Simulate database lookup
            return UserResponse(request.user_id, f"User_{request.user_id}")

    # Order management
    class OrderResponse:
        def __init__(self, order_id: int, total: float):
            self.order_id = order_id
            self.total = total

    class CreateOrderRequest(Request[OrderResponse]):
        def __init__(self, user_id: int, items: list):
            self.user_id = user_id
            self.items = items

    class CreateOrderHandler(Handler[CreateOrderRequest]):
        def __init__(self):
            self.next_order_id = 1000

        def __call__(self, request: CreateOrderRequest) -> OrderResponse:
            total = sum(item["price"] for item in request.items)
            order_id = self.next_order_id
            self.next_order_id += 1
            return OrderResponse(order_id, total)

    # Set up
    resolver = SimpleResolver()
    resolver.register(GetUserRequest, GetUserHandler())
    resolver.register(CreateOrderRequest, CreateOrderHandler())
    mediator = Mediator(resolver)

    # Execute multiple requests
    user = mediator.send(GetUserRequest(42))
    order = mediator.send(
        CreateOrderRequest(42, [{"name": "Item1", "price": 10.0}, {"name": "Item2", "price": 20.0}])
    )

    # Verify
    assert user.user_id == 42
    assert user.name == "User_42"
    assert order.order_id == 1000
    assert order.total == 30.0


def test_handler_composition():
    """Test handlers that depend on other handlers (composition pattern)."""

    # Shared database simulation
    users_db = {}
    posts_db = {}

    # User operations
    class UserCreatedResponse:
        def __init__(self, user_id: int):
            self.user_id = user_id

    class CreateUserRequest(Request[UserCreatedResponse]):
        def __init__(self, name: str):
            self.name = name

    class CreateUserHandler(Handler[CreateUserRequest]):
        def __init__(self):
            self.next_id = 1

        def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
            user_id = self.next_id
            self.next_id += 1
            users_db[user_id] = {"id": user_id, "name": request.name}
            return UserCreatedResponse(user_id)

    # Post operations
    class PostCreatedResponse:
        def __init__(self, post_id: int, user_name: str):
            self.post_id = post_id
            self.user_name = user_name

    class CreatePostRequest(Request[PostCreatedResponse]):
        def __init__(self, user_id: int, content: str):
            self.user_id = user_id
            self.content = content

    class CreatePostHandler(Handler[CreatePostRequest]):
        def __init__(self):
            self.next_post_id = 1

        def __call__(self, request: CreatePostRequest) -> PostCreatedResponse:
            # Validate user exists
            if request.user_id not in users_db:
                raise ValueError("User not found")

            post_id = self.next_post_id
            self.next_post_id += 1
            user_name = users_db[request.user_id]["name"]
            posts_db[post_id] = {
                "id": post_id,
                "user_id": request.user_id,
                "content": request.content,
            }
            return PostCreatedResponse(post_id, user_name)

    # Set up
    resolver = SimpleResolver()
    resolver.register(CreateUserRequest, CreateUserHandler())
    resolver.register(CreatePostRequest, CreatePostHandler())
    mediator = Mediator(resolver)

    # Create user first
    user_response = mediator.send(CreateUserRequest("Bob"))
    user_id = user_response.user_id

    # Then create post for that user
    post_response = mediator.send(CreatePostRequest(user_id, "Hello World!"))

    assert post_response.post_id == 1
    assert post_response.user_name == "Bob"

    # Try to create post for non-existent user
    with pytest.raises(ValueError, match="User not found"):
        mediator.send(CreatePostRequest(999, "Should fail"))


def test_type_safety_at_runtime():
    """Test that type safety is enforced at runtime."""

    class CorrectResponse:
        def __init__(self, value: str):
            self.value = value

    class WrongResponse:
        def __init__(self, value: int):
            self.value = value

    class TypedRequest(Request[CorrectResponse]):
        pass

    # This should fail at class definition time
    with pytest.raises(ResponseTypeMismatchError):

        class WrongHandler(Handler[TypedRequest]):
            def __call__(self, request: TypedRequest) -> WrongResponse:
                return WrongResponse(42)


def test_resolver_switching():
    """Test switching resolvers on mediator."""

    class Resp:
        def __init__(self, source: str):
            self.source = source

    class Req(Request[Resp]):
        pass

    class Handler1(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp("handler1")

    class Handler2(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp("handler2")

    # Create two resolvers with different handlers
    resolver1 = SimpleResolver()
    resolver1.register(Req, Handler1())

    resolver2 = SimpleResolver()
    resolver2.register(Req, Handler2())

    # Use first resolver
    mediator1 = Mediator(resolver1)
    resp1 = mediator1.send(Req())
    assert resp1.source == "handler1"

    # Use second resolver
    mediator2 = Mediator(resolver2)
    resp2 = mediator2.send(Req())
    assert resp2.source == "handler2"
