"""Optional fields and None handling - should pass mypy."""

from dataclasses import dataclass

from pymediate import Handler, Mediator, Request, ServiceCollection


@dataclass
class UserProfileResponse:
    user_id: int
    username: str
    email: str | None = None
    phone: str | None = None


@dataclass
class GetUserProfileRequest(Request[UserProfileResponse]):
    user_id: int


class GetUserProfileHandler(Handler[GetUserProfileRequest]):
    def __call__(self, request: GetUserProfileRequest) -> UserProfileResponse:
        return UserProfileResponse(
            user_id=request.user_id, username="alice", email="alice@example.com", phone=None
        )


# Usage
services = ServiceCollection()
services.add(GetUserProfileRequest, GetUserProfileHandler())
provider = services.build_provider()
mediator = Mediator(provider)

request = GetUserProfileRequest(user_id=1)
response = mediator.send(request)

# Type-safe access with optional fields
user_id: int = response.user_id
username: str = response.username
email: str | None = response.email
phone: str | None = response.phone

# Proper None checking
if response.email is not None:
    email_upper: str = response.email.upper()
