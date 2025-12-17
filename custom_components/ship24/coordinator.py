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
        self._last_error: str | None = None
        self._last_message: str | None = None
        
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

    def _is_retryable_error(self, err: Exception) -> bool:
        """Check if an error is retryable (transient network error).
        
        Args:
            err: The exception to check
            
        Returns:
            True if the error is retryable, False otherwise
        """
        error_str = str(err).lower()
        retryable_keywords = ['timeout', 'dns', 'connection', 'network', 'resolve', 'cannot connect']
        return any(keyword in error_str for keyword in retryable_keywords)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Ship24 API via App Layer."""
        packages = {}
        error_count = 0
        retryable_error_count = 0
        
        for tracking_number in list(self._tracking_numbers):
            try:
                package = await self.api.update_package(tracking_number)
                if package:
                    packages[tracking_number] = package
            except Exception as err:
                error_count += 1
                error_msg = f"Error updating {tracking_number}: {str(err)}"
                
                # Check if this is a retryable error
                if self._is_retryable_error(err):
                    retryable_error_count += 1
                    _LOGGER.warning(
                        "Transient error updating %s (will retry): %s",
                        tracking_number,
                        err
                    )
                else:
                    _LOGGER.error(error_msg)
                
                self._last_error = error_msg
                # Continue with other packages
                continue

        # Update last message
        if error_count == 0:
            self._last_message = f"Successfully updated {len(packages)} packages"
            self._last_error = None
        elif len(packages) > 0:
            self._last_message = f"Updated {len(packages)} packages, {error_count} errors"
        elif retryable_error_count == error_count:
            # All errors are retryable - don't raise UpdateFailed, let coordinator retry
            self._last_message = f"Temporary network issues: {error_count} packages failed (will retry)"
            # Return empty dict but don't raise - coordinator will retry
            self.async_update_listeners()
            return packages
        else:
            # Some non-retryable errors occurred
            self._last_message = f"Failed to update packages: {error_count} errors"
        
        # Trigger update listeners to update logging sensor
        self.async_update_listeners()

        # Only raise UpdateFailed if we have non-retryable errors and no successful updates
        if len(packages) == 0 and retryable_error_count < error_count:
            error_msg = f"Failed to update packages: {error_count} errors"
            self._last_error = error_msg
            raise UpdateFailed(error_msg)
        
        return packages

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
                
                self._last_message = f"Added tracking: {tracking_number}"
                self._last_error = None
                self.async_update_listeners()  # Update logging sensor
                
                await self.async_request_refresh()
                return True
        except Exception as err:
            error_msg = f"Error adding tracking {tracking_number}: {err}"
            _LOGGER.error(error_msg)
            self._last_error = error_msg
            self.async_update_listeners()  # Update logging sensor
        return False

    async def async_remove_tracking(self, tracking_number: str) -> bool:
        """Remove a package from tracking.

        Args:
            tracking_number: The tracking number to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if tracking number exists in our tracking set
            if tracking_number not in self._tracking_numbers:
                _LOGGER.warning("Tracking number %s not found in tracking list", tracking_number)
                return False
            
            # Remove from API layer (this only removes from API cache, not Ship24)
            await self.api.remove_tracking(tracking_number)
            
            # Remove from coordinator tracking
            self.remove_tracking_number(tracking_number)
            
            # Remove entity if callback is available
            if hasattr(self, "_async_remove_entity"):
                try:
                    self._async_remove_entity(tracking_number)
                    _LOGGER.info("Removed entity for tracking number %s", tracking_number)
                except Exception as err:
                    _LOGGER.error("Failed to remove entity for %s: %s", tracking_number, err)
            
            self._last_message = f"Removed tracking: {tracking_number}"
            self._last_error = None
            self.async_update_listeners()  # Update logging sensor
            
            # Don't refresh after removal - the entity is gone
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

