"""
Async HTTP client with retry and error handling
"""

from typing import Optional, Dict, Any
import structlog
import httpx

logger = structlog.get_logger()


class AsyncHTTPClient:
    """
    Async HTTP client wrapper with built-in error handling

    Features:
    - Automatic retry on transient failures
    - Timeout configuration
    - Request logging
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """
        Make GET request

        Args:
            url: URL or path (if base_url set)
            params: Query parameters
            headers: Request headers

        Returns:
            Response object
        """
        client = await self._get_client()

        for attempt in range(self.max_retries):
            try:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries - 1:
                    logger.warning(
                        "HTTP request failed, retrying",
                        url=url,
                        status=e.response.status_code,
                        attempt=attempt + 1
                    )
                    continue
                raise

            except httpx.RequestError as e:
                if attempt < self.max_retries - 1:
                    logger.warning(
                        "HTTP request error, retrying",
                        url=url,
                        error=str(e),
                        attempt=attempt + 1
                    )
                    continue
                raise

    async def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """
        Make POST request

        Args:
            url: URL or path
            json: JSON body
            data: Form data
            headers: Request headers

        Returns:
            Response object
        """
        client = await self._get_client()

        for attempt in range(self.max_retries):
            try:
                response = await client.post(
                    url,
                    json=json,
                    data=data,
                    headers=headers
                )
                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries - 1:
                    continue
                raise

            except httpx.RequestError as e:
                if attempt < self.max_retries - 1:
                    continue
                raise

    async def download(
        self,
        url: str,
        timeout: Optional[float] = None,
    ) -> bytes:
        """
        Download file content

        Args:
            url: URL to download
            timeout: Optional custom timeout

        Returns:
            File content as bytes
        """
        client = await self._get_client()

        if timeout:
            client.timeout = httpx.Timeout(timeout)

        response = await client.get(url)
        response.raise_for_status()

        return response.content

    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
