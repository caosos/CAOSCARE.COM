"""Resend webhook signature verification (Svix format).

Resend delivers webhooks through Svix, not a bespoke scheme - three headers
(svix-id, svix-timestamp, svix-signature) plus a whsec_-prefixed secret.
Verified against Svix's own published algorithm before writing this (see
docs/reports or the inbound-email task's own research trail) rather than
guessed: no `svix` PyPI package dependency was added since the algorithm is
a few lines of stdlib hmac/base64 - one fewer dependency for something this
small and security-sensitive to get to audit directly.

Deliberately pure / no I/O, no DB - fully unit-testable with a fabricated
secret and a hand-signed payload, independent of any live Resend webhook
secret ever being configured.
"""
import base64
import hashlib
import hmac
import time
from typing import Optional

# Reject a signature whose svix-timestamp is further from "now" than this -
# closes the replay window a captured-and-resent request could otherwise use.
MAX_TIMESTAMP_SKEW_SECONDS = 5 * 60


class WebhookVerificationError(Exception):
    """Raised for any reason a webhook request should be rejected -
    missing headers, malformed secret, expired timestamp, or a signature
    that doesn't match. Callers should treat every instance the same way
    (401/400), not branch on the message."""


def _expected_signature(secret: str, svix_id: str, svix_timestamp: str, body: bytes) -> str:
    if not secret.startswith("whsec_"):
        raise WebhookVerificationError("configured webhook secret is not in whsec_... format")
    secret_bytes = base64.b64decode(secret[len("whsec_"):])
    signed_content = f"{svix_id}.{svix_timestamp}.".encode() + body
    digest = hmac.new(secret_bytes, signed_content, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def verify_resend_webhook(
    *, secret: str, svix_id: Optional[str], svix_timestamp: Optional[str],
    svix_signature: Optional[str], body: bytes, now: Optional[float] = None,
) -> None:
    """Raises WebhookVerificationError if the request is not a genuine,
    fresh Resend webhook delivery signed with `secret`. Returns None (no
    value) on success - callers only need to know it didn't raise."""
    if not (svix_id and svix_timestamp and svix_signature):
        raise WebhookVerificationError("missing svix-id/svix-timestamp/svix-signature headers")
    try:
        ts = int(svix_timestamp)
    except ValueError:
        raise WebhookVerificationError("svix-timestamp is not a valid integer")
    if abs((now if now is not None else time.time()) - ts) > MAX_TIMESTAMP_SKEW_SECONDS:
        raise WebhookVerificationError("svix-timestamp is outside the allowed skew window")

    expected = _expected_signature(secret, svix_id, svix_timestamp, body)
    # svix-signature is a space-separated list of "v1,<base64sig>" pairs -
    # more than one only ever appears during Svix's own secret-rotation
    # window, so any single match is sufficient.
    for candidate in svix_signature.split():
        version, _, sig = candidate.partition(",")
        if version != "v1" or not sig:
            continue
        if hmac.compare_digest(sig, expected):
            return
    raise WebhookVerificationError("signature does not match")
