import asyncio
import aiohttp
import logging
import time
import functools
from aiohttp import ClientResponseError
from .const import DEFAULT_API_URL, DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState
from homeassistant.exceptions import ConfigEntryAuthFailed

_LOGGER = logging.getLogger(__name__)

# Client-side rate limiting: max 60 requests per 60s sliding window.
# Prevents HTTP 429 with many devices/hubs in high-frequency polling environments.
_RATE_LIMIT_REQUESTS = 60
_RATE_LIMIT_WINDOW   = 60  # seconds

# Retry with exponential backoff on transient network errors.
# 2 additional attempts (3 total): 1s → 2s → exception propagated.
_MAX_RETRIES        = 2
_RETRY_BACKOFF_BASE = 1.0   # seconds
_RETRY_BACKOFF_MAX  = 10.0  # seconds

# Arming command retry parameters.
# The Ajax server imposes a hard limit of 100 req/min.  On HTTP 429 (or a
# rate-limit body message) we wait _ARMING_RETRY_WAIT seconds and retry,
# up to _MAX_ARMING_RETRIES times before raising AjaxAPIError.
# Same mechanism applies to any 5xx server error during arming.
_MAX_ARMING_RETRIES = 50
_ARMING_RETRY_WAIT  = 0.5   # seconds between arming retries


class AjaxAPIError(Exception):
    """Exception raised for Ajax API errors."""
    pass

def handle_unauthorized(func):
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except ClientResponseError as e:
            if e.status == 401:
                _LOGGER.warning("Unauthorized! Trying to refresh token...")
                try:
                    await self.update_refresh_token()
                    return await func(self, *args, **kwargs)
                except Exception as refresh_error:
                    _LOGGER.error("Token refresh failed: %s", refresh_error)
                    raise
            raise
    return wrapper

class AjaxAPI:
    base_url = DEFAULT_API_URL

    def __init__(self, data, hass=None, entry=None, session=None):
        self.session_token = data["session_token"]
        self.user_id = data["user_id"]
        self.refresh_token = data["refresh_token"]
        self.hass = hass
        self.entry = entry
        self.session = session
        self.headers = {
            "X-Session-Token": self.session_token
        }
        self.session_created_at = data.get("token_created_at", time.time())
        self._reauth_in_progress = False
        # Lock to prevent concurrent token refresh requests.
        # Without this, N coordinators seeing an expired token simultaneously
        # would all call POST /api/refresh with the same refresh_token —
        # the server invalidates duplicates, causing false ConfigEntryAuthFailed.
        self._token_refresh_lock = asyncio.Lock()
        # Sliding window timestamps for rate limiting.
        self._request_timestamps: list[float] = []
        self._rate_limit_lock = asyncio.Lock()

    # ── Rate limiting ─────────────────────────────────────────────────────────

    async def _check_rate_limit(self) -> None:
        """Enforce client-side rate limiting (max 60 req/60s, sliding window).

        Sleep is performed outside the lock so other coroutines are not blocked
        while waiting.
        """
        wait_time = 0.0
        async with self._rate_limit_lock:
            now = time.time()
            self._request_timestamps = [
                ts for ts in self._request_timestamps
                if now - ts < _RATE_LIMIT_WINDOW
            ]
            if len(self._request_timestamps) >= _RATE_LIMIT_REQUESTS:
                oldest = self._request_timestamps[0]
                wait_time = _RATE_LIMIT_WINDOW - (now - oldest)

        if wait_time > 0:
            _LOGGER.warning(
                "Rate limit reached (%d req/%ds) — waiting %.1fs",
                _RATE_LIMIT_REQUESTS, _RATE_LIMIT_WINDOW, wait_time,
            )
            await asyncio.sleep(wait_time)

        async with self._rate_limit_lock:
            self._request_timestamps.append(time.time())

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        """Return exponential backoff delay for the given attempt index."""
        return min(_RETRY_BACKOFF_BASE * (2 ** attempt), _RETRY_BACKOFF_MAX)

    @staticmethod
    def _detect_rate_limit(status: int, data) -> bool:
        """Return True if the server response indicates a rate limit.

        Handles both HTTP 429 and Ajax-specific HTTP 200 bodies that contain
        "exceeded the limit" (observed during real API tests with 100 req/min limit).
        """
        if status == 429:
            return True
        if isinstance(data, dict):
            msg = data.get("message", "").lower()
            return "exceeded the limit" in msg or "too many requests" in msg
        if isinstance(data, str):
            low = data.lower()
            return "exceeded the limit" in low or "too many requests" in low
        return False

    async def _arm_command_with_retry(self, hub_id: str, command: str) -> None:
        """POST /api/hub/arming and retry until 200/204 OK.

        Retry policy (max _MAX_ARMING_RETRIES = 50, wait _ARMING_RETRY_WAIT = 0.5s):
          - HTTP 200/204          → success, return immediately.
          - HTTP 429 / rate-limit → wait 500ms and retry.
          - HTTP 5xx server error → wait 500ms and retry.
          - Network timeout/error → wait 500ms and retry.
          - HTTP 4xx (non-429)    → not retriable, raise AjaxAPIError immediately.
          - Exceeded max retries  → raise AjaxAPIError.
        """
        url = f"{self.base_url}/api/hub/arming"
        payload = {
            "user_id": self.user_id,
            "hub_id": hub_id,
            "session_token": self.session_token,
            "command": command,
        }
        for attempt in range(_MAX_ARMING_RETRIES + 1):
            try:
                async with self.session.post(url, json=payload) as resp:
                    if resp.status in (200, 204):
                        _LOGGER.debug(
                            "arm %s hub %s: OK on attempt %d",
                            command, hub_id, attempt + 1,
                        )
                        return
                    # Read body for diagnostics and rate-limit detection.
                    try:
                        result = await resp.json(content_type=None)
                    except Exception:
                        result = await resp.text()
                    status = resp.status

                if self._detect_rate_limit(status, result):
                    if attempt < _MAX_ARMING_RETRIES:
                        _LOGGER.warning(
                            "arm %s hub %s: rate limited (attempt %d/%d) — retrying in %.1fs",
                            command, hub_id, attempt + 1, _MAX_ARMING_RETRIES, _ARMING_RETRY_WAIT,
                        )
                        await asyncio.sleep(_ARMING_RETRY_WAIT)
                        continue
                    raise AjaxAPIError(
                        f"arm {command}: rate limited after {_MAX_ARMING_RETRIES} retries"
                    )

                if status >= 500:
                    if attempt < _MAX_ARMING_RETRIES:
                        _LOGGER.warning(
                            "arm %s hub %s: server error HTTP %d (attempt %d/%d) — retrying in %.1fs",
                            command, hub_id, status, attempt + 1, _MAX_ARMING_RETRIES, _ARMING_RETRY_WAIT,
                        )
                        await asyncio.sleep(_ARMING_RETRY_WAIT)
                        continue
                    raise AjaxAPIError(
                        f"arm {command}: server error {status} after {_MAX_ARMING_RETRIES} retries"
                    )

                # 4xx other than 429 — not retriable.
                _LOGGER.error(
                    "arm %s hub %s: unexpected HTTP %d: %.300s",
                    command, hub_id, status, str(result),
                )
                raise AjaxAPIError(f"arm {command}: unexpected status {status}")

            except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as exc:
                if attempt < _MAX_ARMING_RETRIES:
                    _LOGGER.warning(
                        "arm %s hub %s: network error (attempt %d/%d): %s — retrying in %.1fs",
                        command, hub_id, attempt + 1, _MAX_ARMING_RETRIES, exc, _ARMING_RETRY_WAIT,
                    )
                    await asyncio.sleep(_ARMING_RETRY_WAIT)
                else:
                    raise AjaxAPIError(
                        f"arm {command}: network error after {_MAX_ARMING_RETRIES} retries: {exc}"
                    ) from exc

        raise AjaxAPIError(f"arm {command}: failed after {_MAX_ARMING_RETRIES} retries")

    def is_token_expired(self):
        # Threshold set to 12 minutes (3-minute safety margin before actual ~15-min expiry).
        return time.time() - self.session_created_at > 12 * 60

    def is_refresh_token_old(self):
        # Refresh token expires after 7 days
        token_created_at = self.entry.data.get("token_created_at", 0) if self.entry else 0
        return time.time() - token_created_at > 7 * 24 * 60 * 60

    async def ensure_token_valid(self):
        """Check and renew the session token if expired.

        Uses double-checked locking with asyncio.Lock:
        1. Initial check without lock (fast path — token is usually valid)
        2. If expired: acquire the lock
        3. Re-check inside the lock (first caller already renewed the token)
        4. Only the first caller executes update_refresh_token(); others exit at re-check

        This prevents N parallel calls to POST /api/refresh using the same
        refresh_token, which would cause server-side invalidation of duplicates.
        """
        if self.is_token_expired():
            async with self._token_refresh_lock:
                if self.is_token_expired():  # re-check inside lock: only first caller proceeds
                    _LOGGER.debug("Token expired, refreshing...")
                    await self.update_refresh_token()


    async def update_refresh_token(self):
        _LOGGER.debug("Refreshing token")
        try:
            # Timeout of 15s prevents indefinite block if the server is unresponsive,
            # which would stall all coordinators sharing this API instance.
            async with self.session.post(
                f"{self.base_url}/api/refresh",
                json={
                    "user_id": self.user_id,
                    "refresh_token": self.refresh_token
                },
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:

                if resp.status == 401 or resp.status == 403:
                    text = await resp.text()
                    _LOGGER.error("Refresh token unauthorized: %s %s", resp.status, text)
                    raise ConfigEntryAuthFailed(f"Unauthorized refresh token: {resp.status}")

                resp.raise_for_status()

                data = await resp.json()

        except (ConfigEntryAuthFailed, AjaxAPIError):
            raise  # preserve already-classified exceptions
        except aiohttp.ClientResponseError as e:
            # HTTP 429 = temporary rate limit → AjaxAPIError (coordinator retries next cycle)
            # All other HTTP errors → ConfigEntryAuthFailed (triggers reauth)
            if e.status == 429:
                _LOGGER.warning("Rate limit (HTTP 429) during token refresh, retrying next cycle: %s", e)
                raise AjaxAPIError(f"Rate limited (HTTP 429): {e}") from e
            _LOGGER.error("HTTP error during token refresh: %s", e)
            raise ConfigEntryAuthFailed(f"HTTP error: {e}") from e
        except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as e:
            # Transient network errors → AjaxAPIError (coordinator retries next cycle)
            # NOT ConfigEntryAuthFailed: a network timeout must not force re-authentication
            _LOGGER.warning("Network error during token refresh, retrying next cycle: %s", e)
            raise AjaxAPIError(f"Network error during token refresh: {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error during token refresh: %s", e)
            raise ConfigEntryAuthFailed(f"Unexpected error: {e}") from e

        if "sessionToken" not in data or "refreshToken" not in data:
            msg = data.get("message", "")
            # Ajax server returns HTTP 200 with {"message": "You have exceeded the limit..."}
            # for rate limiting. This is NOT an auth failure — treat as temporary error.
            # Raising AjaxAPIError → coordinator converts to UpdateFailed → automatic retry
            # instead of ConfigEntryAuthFailed → unnecessary forced re-authentication.
            if "exceeded the limit" in msg or "too many requests" in msg.lower():
                _LOGGER.warning("Rate limit during token refresh, retrying next cycle: %s", msg)
                raise AjaxAPIError(f"Rate limited by server: {msg}")
            _LOGGER.error("Failed to refresh token! Response: %s", data)
            raise ConfigEntryAuthFailed(f"Refresh token expired or invalid: {data}")

        self.session_token = data["sessionToken"]
        self.refresh_token = data["refreshToken"]
        self.headers["X-Session-Token"] = self.session_token
        self.session_created_at = time.time()

        # Save new tokens to config entry
        _LOGGER.debug("Saving refreshed tokens to config entry")
        if self.hass and self.entry:
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={
                    **self.entry.data,
                    "session_token": self.session_token,
                    "refresh_token": self.refresh_token,
                    "token_created_at": self.session_created_at,
                }
            )
            # Also update runtime data cache to keep both paths consistent
            if hasattr(self.hass, "data") and self.entry.entry_id in self.hass.data.get(DOMAIN, {}):
                self.hass.data[DOMAIN][self.entry.entry_id].update({
                    "session_token": self.session_token,
                    "refresh_token": self.refresh_token,
                    "token_created_at": self.session_created_at,
                })
            _LOGGER.debug("Entry updated with new tokens")
            return True
        # Fallback path: guard against missing entry_id to avoid KeyError
        # during abnormal startup/teardown scenarios.
        if (hasattr(self.hass, "data") and hasattr(self.entry, "domain") and
                self.entry.entry_id in self.hass.data.get(self.entry.domain, {})):
            self.hass.data[self.entry.domain][self.entry.entry_id].update({
                "session_token": self.session_token,
                "refresh_token": self.refresh_token,
                "token_created_at": self.session_created_at,
            })
            _LOGGER.debug("Runtime data updated with new tokens")
            return True
        _LOGGER.warning("Could not persist refreshed tokens — hass or entry not available")
        return False


    @handle_unauthorized
    async def get_hubs(self):
        await self.ensure_token_valid()
        _LOGGER.debug("Fetching hubs")
        async with self.session.get(
            f"{self.base_url}/api/hubs",
                json={
                    "user_id": self.user_id,
                    "session_token": self.session_token
                }
        ) as resp:
            status = resp.status
            data = await resp.json()

        # Rate limit: raise AjaxAPIError so coordinator/setup retry logic kicks in.
        if self._detect_rate_limit(status, data):
            msg = data.get("message", str(data)) if isinstance(data, dict) else str(data)
            _LOGGER.warning("get_hubs: rate limited by server: %s", msg)
            raise AjaxAPIError(f"get_hubs rate limited: {msg}")

        if isinstance(data, dict) and data.get("message") == "User is not authorized":
            _LOGGER.warning("User is not authorized in get_hubs response: %s", data)

            refreshed = await self.update_refresh_token()
            _LOGGER.debug("Token refresh result: %s", refreshed)

            if not refreshed:
                raise ConfigEntryAuthFailed
            # Single retry after refresh — avoids infinite recursion if the API
            # keeps returning "not authorized" despite a successful token refresh.
            async with self.session.get(
                f"{self.base_url}/api/hubs",
                    json={
                        "user_id": self.user_id,
                        "session_token": self.session_token
                    }
            ) as resp:
                data = await resp.json()
            if isinstance(data, dict) and data.get("message") == "User is not authorized":
                raise ConfigEntryAuthFailed("Still unauthorized after token refresh")

        if not isinstance(data, list):
            _LOGGER.error("Expected list of hubs, got: %s", type(data))
            _LOGGER.debug("Hubs response: %s", data)
            return []

        return data

    @handle_unauthorized
    async def get_hub_info(self, hub_id):
        """Fetch hub info and state with rate limiting and retry on network errors."""
        start = time.perf_counter()
        await self.ensure_token_valid()
        await self._check_rate_limit()

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                delay = self._backoff_delay(attempt - 1)
                _LOGGER.warning(
                    "Hub %s: retry %d/%d after network error (waiting %.1fs)",
                    hub_id, attempt, _MAX_RETRIES, delay,
                )
                await asyncio.sleep(delay)
            try:
                async with self.session.post(
                    f"{self.base_url}/api/hub_info",
                    json={
                        "user_id": self.user_id,
                        "hub_id": hub_id,
                        "session_token": self.session_token
                    }
                ) as resp:
                    hub_info_status = resp.status
                    info = await resp.json()

                # Rate limit: raise AjaxAPIError (coordinator converts to UpdateFailed → retry).
                if self._detect_rate_limit(hub_info_status, info):
                    msg = info.get("message", str(info)) if isinstance(info, dict) else str(info)
                    _LOGGER.warning("get_hub_info hub %s: rate limited: %s", hub_id, msg)
                    raise AjaxAPIError(f"get_hub_info rate limited: {msg}")

                break  # success — exit loop
            except AjaxAPIError:
                raise  # propagate rate-limit errors without consuming retry budget
            except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as e:
                last_exc = e
                if attempt == _MAX_RETRIES:
                    _LOGGER.error("Hub %s: max retries reached: %s", hub_id, e)
                    raise AjaxAPIError(f"Network error after {_MAX_RETRIES} retries: {e}") from e
        else:
            raise AjaxAPIError(f"get_hub_info failed after {_MAX_RETRIES} retries") from last_exc

        if info.get("message") == "User is not authorized":
            _LOGGER.warning("User not authorized in hub_info body, refreshing token...")
            await self.update_refresh_token()
            async with self.session.post(
                f"{self.base_url}/api/hub_info",
                json={
                    "user_id": self.user_id,
                    "hub_id": hub_id,
                    "session_token": self.session_token
                }
            ) as resp:
                info = await resp.json()

        if "state" not in info:
            _LOGGER.error("No 'state' in hub info response: %s", info)
            return None
        _LOGGER.debug("API get hub info_time: %.2f sec", time.perf_counter() - start)
        _LOGGER.debug("API get hub info state: %s", info.get("state"))
        return info

    @handle_unauthorized
    async def arm_hub(self, hub_id):
        """Arm the hub (AWAY mode).  Retries up to 50 times on rate limit / server errors."""
        await self.ensure_token_valid()
        await self._arm_command_with_retry(hub_id, "ARM")

    @handle_unauthorized
    async def disarm_hub(self, hub_id):
        """Disarm the hub.  Retries up to 50 times on rate limit / server errors."""
        await self.ensure_token_valid()
        await self._arm_command_with_retry(hub_id, "DISARM")

    @handle_unauthorized
    async def arm_hub_night(self, hub_id):
        """Arm the hub in NIGHT mode.  Retries up to 50 times on rate limit / server errors."""
        await self.ensure_token_valid()
        await self._arm_command_with_retry(hub_id, "NIGHT_MODE_ON")

    @handle_unauthorized
    async def get_hub_devices(self, hub_id):
        await self.ensure_token_valid()
        async with (self.session.post(
                f"{self.base_url}/api/hub_devices",
                json={
                    "user_id": self.user_id,
                    "hub_id": hub_id,
                    "session_token": self.session_token
                })
        as resp):
            if resp.status == 204:
                _LOGGER.info("No content returned for devices.")
                return None
            # content_type=None: same fix as arm commands — handles non-JSON error responses.
            try:
                result = await resp.json(content_type=None)
            except Exception:
                _LOGGER.error(
                    "hub_devices: unparseable response (HTTP %d, Content-Type: %s)",
                    resp.status, resp.headers.get("Content-Type", "?"),
                )
                return None
        return result

    @handle_unauthorized
    async def get_device_info(self, hub_id, device_id):
        """Fetch device info and state with rate limiting and retry on network errors."""
        start = time.perf_counter()
        await self.ensure_token_valid()
        await self._check_rate_limit()

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                delay = self._backoff_delay(attempt - 1)
                _LOGGER.warning(
                    "Device %s: retry %d/%d after network error (waiting %.1fs)",
                    device_id, attempt, _MAX_RETRIES, delay,
                )
                await asyncio.sleep(delay)
            try:
                async with self.session.post(
                    f"{self.base_url}/api/device_info",
                    json={
                        "user_id": self.user_id,
                        "hub_id": hub_id,
                        "device_id": device_id,
                        "session_token": self.session_token
                    }
                ) as resp:
                    hit = resp.headers.get("X-Ajax-Origin-Hit")
                    _LOGGER.debug("ajax origin hit=%s", hit)
                    if resp.status == 204:
                        _LOGGER.info("No content returned for device info.")
                        return None
                    dev_status = resp.status
                    result = await resp.json()

                # Rate limit: raise AjaxAPIError (coordinator converts to UpdateFailed → retry).
                if self._detect_rate_limit(dev_status, result):
                    msg = result.get("message", str(result)) if isinstance(result, dict) else str(result)
                    _LOGGER.warning("get_device_info device %s: rate limited: %s", device_id, msg)
                    raise AjaxAPIError(f"get_device_info rate limited: {msg}")

                break  # success — exit loop
            except AjaxAPIError:
                raise  # propagate rate-limit errors without consuming retry budget
            except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as e:
                last_exc = e
                if attempt == _MAX_RETRIES:
                    _LOGGER.error("Device %s: max retries reached: %s", device_id, e)
                    raise AjaxAPIError(f"Network error after {_MAX_RETRIES} retries: {e}") from e
        else:
            raise AjaxAPIError(f"get_device_info failed after {_MAX_RETRIES} retries") from last_exc

        _LOGGER.debug("API get DEVICE info_time: %.2f sec", time.perf_counter() - start)
        return result
