from pydantic import BaseModel, Field

from app.modules.auth.domain.results import LoginResult
from app.modules.auth.domain.identity import CustomerIdentity


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    phone: str = Field(min_length=8, max_length=32)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class CustomerIdentityResponse(BaseModel):
    customer_id: int
    name: str
    email: str
    phone: str
    city: str

    @classmethod
    def from_domain(
        cls, customer: CustomerIdentity
    ) -> "CustomerIdentityResponse":
        return cls(
            customer_id=customer.customer_id,
            name=customer.name,
            email=customer.email,
            phone=customer.phone,
            city=customer.city,
        )


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    customer: CustomerIdentityResponse

    @classmethod
    def from_result(cls, result: LoginResult) -> "LoginResponse":
        return cls(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_in=result.access_expires_in,
            refresh_expires_in=result.refresh_expires_in,
            customer=CustomerIdentityResponse.from_domain(result.customer),
        )


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
