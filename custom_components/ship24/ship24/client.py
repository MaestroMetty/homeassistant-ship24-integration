"""Ship24 API client - Direct HTTP communication with Ship24 API."""

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from ..const import (
    SHIP24_API_BASE_URL,
    SHIP24_API_TRACKERS_ENDPOINT,
    SHIP24_API_TRACKERS_TRACK_ENDPOINT,
    SHIP24_API_TRACKERS_SEARCH_ENDPOINT,
    SHIP24_API_WEBHOOKS_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


class Ship24Client:
    """Client for interacting with Ship24 API."""

    def __init__(self, api_key: str, session: Optional[aiohttp.ClientSession] = None):
        """Initialize Ship24 client.

        Args:
            api_key: Ship24 API key
            session: Optional aiohttp session (will create one if not provided)
        """
        self._api_key = api_key
        self._session = session
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._base_url = SHIP24_API_BASE_URL

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to Ship24 API.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            aiohttp.ClientError: On HTTP errors
        """
        url = f"{self._base_url}{endpoint}"
        session = self._session or aiohttp.ClientSession()

        try:
            async with session.request(
                method, url, headers=self._headers, json=data, params=params
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as err:
            _LOGGER.error("Ship24 API request failed: %s", err)
            raise
        finally:
            if not self._session:
                await session.close()

    async def get_trackers_list(self) -> List[Dict[str, Any]]:
        """Get list of all trackers.

        Returns:
            List of tracker objects (only isSubscribed=true and isTracked=true)
        """
        try:
            response = await self._request("GET", SHIP24_API_TRACKERS_ENDPOINT)
            trackers = response.get("data", {}).get("trackers", [])
            # Filter only active trackers
            return [
                t
                for t in trackers
                if t.get("isSubscribed") is True and t.get("isTracked") is True
            ]
        except Exception as err:
            _LOGGER.error("Failed to get trackers list: %s", err)
            return []

    async def find_tracker(self, tracking_number: str) -> Optional[Dict[str, Any]]:
        """Find a tracker by tracking number in the list.

        Args:
            tracking_number: The tracking number to find

        Returns:
            Tracker object if found, None otherwise
        """
        trackers = await self.get_trackers_list()
        for tracker in trackers:
            if tracker.get("trackingNumber") == tracking_number:
                return tracker
        return None

    async def create_tracker(
        self, tracking_number: str, carrier_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new tracker or get existing one.

        Args:
            tracking_number: The tracking number to track
            carrier_code: Optional carrier code (for faster tracking)

        Returns:
            Ship24 API response with tracker data
        """
        # First check if tracker already exists
        existing = await self.find_tracker(tracking_number)
        if existing:
            _LOGGER.info("Tracker %s already exists, fetching results", tracking_number)
            # Get full tracking results
            return await self.get_tracker_results(tracking_number)

        # Create new tracker using /trackers/track endpoint
        data = {"trackingNumber": tracking_number}
        if carrier_code:
            data["courierCode"] = carrier_code

        return await self._request("POST", SHIP24_API_TRACKERS_TRACK_ENDPOINT, data=data)

    async def get_tracker_results(self, tracking_number: str) -> Dict[str, Any]:
        """Get tracker results using search endpoint.

        Args:
            tracking_number: The tracking number

        Returns:
            Ship24 API response with tracking results
        """
        endpoint = f"{SHIP24_API_TRACKERS_SEARCH_ENDPOINT}/{tracking_number}/results"
        return await self._request("GET", endpoint)

    async def get_tracker(self, tracking_number: str) -> Dict[str, Any]:
        """Get tracker data (alias for get_tracker_results).

        Args:
            tracking_number: The tracking number

        Returns:
            Ship24 API response with tracker data
        """
        return await self.get_tracker_results(tracking_number)

    async def delete_tracker(self, tracking_number: str) -> bool:
        """Delete a tracker.

        Args:
            tracking_number: The tracking number to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            endpoint = f"{SHIP24_API_TRACKERS_ENDPOINT}/{tracking_number}"
            await self._request("DELETE", endpoint)
            return True
        except Exception:
            return False

    async def register_webhook(self, webhook_url: str) -> Optional[str]:
        """Register a webhook URL.

        Args:
            webhook_url: The webhook URL to register

        Returns:
            Webhook ID if successful, None otherwise
        """
        try:
            data = {"url": webhook_url}
            response = await self._request("POST", SHIP24_API_WEBHOOKS_ENDPOINT, data=data)
            return response.get("data", {}).get("webhookId")
        except Exception as err:
            _LOGGER.error("Failed to register webhook: %s", err)
            return None

    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook.

        Args:
            webhook_id: The webhook ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            endpoint = f"{SHIP24_API_WEBHOOKS_ENDPOINT}/{webhook_id}"
            await self._request("DELETE", endpoint)
            return True
        except Exception:
            return False

    async def test_connection(self) -> bool:
        """Test API connection by making a simple request.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to get trackers list (empty is fine, just testing auth)
            await self._request("GET", SHIP24_API_TRACKERS_ENDPOINT, params={"limit": 1})
            return True
        except Exception:
            return False

