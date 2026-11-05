from app.core.exceptions import AuthenticationError


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"
    message = "Invalid e-mail or phone"


class MissingTokenError(AuthenticationError):
    code = "missing_token"
    message = "Authentication token is required"


class InvalidTokenError(AuthenticationError):
    code = "invalid_token"
    message = "Authentication token is invalid"


class ExpiredTokenError(AuthenticationError):
    code = "expired_token"
    message = "Authentication token has expired"
