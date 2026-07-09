"""Basic type inference through mediator.send() - should pass mypy."""

from dataclasses import dataclass

from pymediate import Handler, Mediator, Request, Services


@dataclass
class UserResponse:
    user_id: int
    username: str


@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int


class GetUserHandler(Handler[GetUserRequest]):
    def __call__(self, request: GetUserRequest) -> UserResponse:
        return UserResponse(user_id=request.user_id, username="alice")


# Setup
services = Services()
services.add(GetUserHandler())
provider = services.provider()
mediator = Mediator(provider)

# Type inference test
request = GetUserRequest(user_id=1)
response = mediator.send(request)

# Mypy should know response is UserResponse
user_id: int = response.user_id
username: str = response.username
