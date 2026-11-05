import ipaddress
from urllib.parse import urlparse

from app.modules.messages.application.exceptions import InvalidWebhookUrlError

MAX_WEBHOOK_URL_LENGTH = 2048


def validate_webhook_url(
    url: str, *, allow_private_hosts: bool
) -> str:
    value = url.strip()
    if not value or len(value) > MAX_WEBHOOK_URL_LENGTH:
        raise InvalidWebhookUrlError()

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidWebhookUrlError()
    if parsed.username or parsed.password:
        raise InvalidWebhookUrlError()

    host = parsed.hostname.lower()
    if allow_private_hosts:
        return value

    if host in {"localhost", "localhost.localdomain"}:
        raise InvalidWebhookUrlError()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return value
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    ):
        raise InvalidWebhookUrlError()
    return value
