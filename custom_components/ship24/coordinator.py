"""DataUpdateCoordinator for Ship24 integration."""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from homeassistant.config_entries import ConfigEntry

from .app.api import ParcelTrackingAPI
from .const import CONF_TRACKING_NUMBERS, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class Ship24DataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Ship24 data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: ParcelTrackingAPI,
        entry: ConfigEntry,
        update_interval: int = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize coordinator."""
        self.api = api
        self.hass = hass
        self.entry = entry
        self._tracking_numbers: set[str] = set()
        
        # Load tracking numbers from config entry
        saved_tracking_numbers = entry.data.get(CONF_TRACKING_NUMBERS, [])
        if isinstance(saved_tracking_numbers, list):
            self._tracking_numbers = set(saved_tracking_numbers)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    def add_tracking_number(self, tracking_number: str) -> None:
        """Add a tracking number to be monitored."""
        self._tracking_numbers.add(tracking_number)
        self._save_tracking_numbers()
        # Trigger immediate update
        self.async_update_listeners()

    def remove_tracking_number(self, tracking_number: str) -> None:
        """Remove a tracking number from monitoring."""
        self._tracking_numbers.discard(tracking_number)
        self._save_tracking_numbers()

    def get_tracking_numbers(self) -> set[str]:
        """Get all tracking numbers being monitored."""
        return self._tracking_numbers.copy()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Ship24 API via App Layer."""
        try:
            packages = {}
            for tracking_number in list(self._tracking_numbers):
                try:
                    package = await self.api.update_package(tracking_number)
                    if package:
                        packages[tracking_number] = package
                except Exception as err:
                    _LOGGER.error(
                        "Error updating package %s: %s", tracking_number, err
                    )
                    # Continue with other packages
                    continue

            return packages
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_add_tracking(
        self, tracking_number: str, custom_name: str | None = None
    ) -> bool:
        """Add a new package to track.

        Args:
            tracking_number: The tracking number
            custom_name: Optional custom name

        Returns:
            True if successful, False otherwise
        """
        try:
            package = await self.api.add_tracking(tracking_number, custom_name)
            if package:
                was_new = tracking_number not in self._tracking_numbers
                self.add_tracking_number(tracking_number)
                # Create sensor entity if callback is available and this is a new package
                if was_new and hasattr(self, "_async_add_entities"):
                    from .sensor import Ship24PackageSensor
                    sensor = Ship24PackageSensor(self, tracking_number)
                    self._async_add_entities([sensor])
                await self.async_request_refresh()
                return True
        except Exception as err:
            _LOGGER.error("Error adding tracking %s: %s", tracking_number, err)
        return False

    async def async_remove_tracking(self, tracking_number: str) -> bool:
        """Remove a package from tracking.

        Args:
            tracking_number: The tracking number to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            success = await self.api.remove_tracking(tracking_number)
            if success:
                self.remove_tracking_number(tracking_number)
                await self.async_request_refresh()
                return True
        except Exception as err:
            _LOGGER.error("Error removing tracking %s: %s", tracking_number, err)
        return False

    async def async_update_package(self, tracking_number: str) -> None:
        """Manually trigger update for a specific package."""
        try:
            await self.api.update_package(tracking_number)
            await self.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Error updating package %s: %s", tracking_number, err)

    def _save_tracking_numbers(self) -> None:
        """Save tracking numbers to config entry."""
        if not self.entry:
            return
        
        # Update config entry data
        new_data = {**self.entry.data, CONF_TRACKING_NUMBERS: list(self._tracking_numbers)}
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)

