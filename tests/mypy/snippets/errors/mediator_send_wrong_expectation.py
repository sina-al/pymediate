"""Expecting wrong response type from mediator.send() - should fail mypy."""

from dataclasses import dataclass

from pymediate import Handler, Mediator, Request, SimpleResolver


@dataclass
class UserResponse:
    user_id: int
    username: str


@dataclass
class ProductResponse:
    product_id: int
    name: str


@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int


class GetUserHandler(Handler[GetUserRequest]):
    def __call__(self, request: GetUserRequest) -> UserResponse:
        return UserResponse(user_id=1, username="alice")


resolver = SimpleResolver()
resolver.register(GetUserRequest, GetUserHandler())
mediator = Mediator(resolver)

request = GetUserRequest(user_id=1)

# ERROR: mediator.send returns UserResponse, not ProductResponse
response: ProductResponse = mediator.send(request)
