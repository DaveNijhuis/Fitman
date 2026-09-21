from slowapi import Limiter
from slowapi.util import get_remote_address

from config import settings

# RATE_LIMIT_DISABLED=true disables the limiter for E2E test environments.
# All other environments (production, CI backend tests) leave it enabled.
limiter = Limiter(key_func=get_remote_address, enabled=not settings.rate_limit_disabled)
