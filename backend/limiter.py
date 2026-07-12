import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# RATE_LIMIT_DISABLED=true disables the limiter for E2E test environments.
# All other environments (production, CI backend tests) leave it enabled.
_enabled = os.getenv("RATE_LIMIT_DISABLED", "").lower() != "true"

limiter = Limiter(key_func=get_remote_address, enabled=_enabled)
