import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 15.0
DEFAULT_USER_AGENT = "confwall/0.1.0"
MAX_ATTEMPTS = 3
INITIAL_BACKOFF = 0.5


class HttpClient:
    def __init__(
        self,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: Any = None,
    ) -> requests.Response:
        attempt = 0
        backoff = INITIAL_BACKOFF
        last_exception: Exception | None = None

        req_headers = dict(headers) if headers else {}

        while attempt < MAX_ATTEMPTS:
            attempt += 1
            try:
                logger.debug(f"HTTP {method} {url} (attempt {attempt}/{MAX_ATTEMPTS})")
                resp = self.session.request(
                    method=method,
                    url=url,
                    headers=req_headers,
                    params=params,
                    data=data,
                    timeout=(self.connect_timeout, self.read_timeout),
                )

                # 4xx is our fault and won't change on retry, apart from timeout and rate limit.
                if 400 <= resp.status_code < 500 and resp.status_code not in (408, 429):
                    resp.raise_for_status()
                    return resp

                if resp.status_code >= 500 or resp.status_code in (408, 429):
                    if attempt < MAX_ATTEMPTS:
                        logger.warning(
                            f"HTTP {resp.status_code} for {url}, retrying in {backoff}s..."
                        )
                        time.sleep(backoff)
                        backoff *= 2
                        continue

                resp.raise_for_status()
                return resp

            except (requests.Timeout, requests.ConnectionError) as e:
                last_exception = e
                if attempt < MAX_ATTEMPTS:
                    logger.warning(
                        f"Network error ({e}) requesting {url}, retrying in {backoff}s..."
                    )
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise RuntimeError(
                        f"Failed to fetch {url} after {MAX_ATTEMPTS} attempts: {e}"
                    ) from e
            except requests.HTTPError as e:
                raise RuntimeError(
                    f"HTTP error {e.response.status_code} requesting {url}: {e}"
                ) from e

        if last_exception:
            raise RuntimeError(
                f"Failed to fetch {url} after {MAX_ATTEMPTS} attempts: {last_exception}"
            )
        raise RuntimeError(f"Failed to fetch {url}")

    def get_bytes(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        resp = self.request("GET", url, headers=headers)
        return resp.content

    def get_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        resp = self.request("GET", url, headers=headers, params=params)
        return resp.json()
