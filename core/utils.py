"""
core/utils.py

Shared utility functions used across the SMEC backend.

Currently contains:
  - get_client_ip: extract the real client IP from a Django request,
    accounting for reverse proxies (Nginx, Cloudflare, etc.)
"""


def get_client_ip(request):
    """
    Extract the real client IP address from an HTTP request.

    When Django sits behind a reverse proxy (Nginx, Cloudflare, load
    balancer), the client IP is passed via the X-Forwarded-For header.
    The format is:  X-Forwarded-For: client, proxy1, proxy2
    The first IP in the list is the original client.

    Args:
        request: Django HttpRequest object

    Returns:
        str: The real client IP address, or None if unavailable.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if x_forwarded_for:
        # Take the first IP — the original client
        # Strip whitespace that some proxies add after the comma
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        # No proxy — REMOTE_ADDR is the direct client
        ip = request.META.get("REMOTE_ADDR")

    return ip or None
