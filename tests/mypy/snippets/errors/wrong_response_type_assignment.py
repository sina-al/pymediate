"""Assigning response to wrong type - should fail mypy."""

from dataclasses import dataclass

from pymediate import Handler, Mediator, Request, Services


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
        return UserResponse(user_id=request.user_id, username="alice")


services = Services()
services.add(GetUserRequest, GetUserHandler())
provider = services.provider()
mediator = Mediator(provider)

request = GetUserRequest(user_id=1)

# ERROR: Cannot assign UserResponse to ProductResponse
response: ProductResponse = mediator.send(request)
