"""Button entities for Ship24 package tracking."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_IDENTIFIER, DEVICE_NAME, DOMAIN
from .coordinator import Ship24DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ship24 button from a config entry."""
    coordinator: Ship24DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # Get the async_add_sensor callback from coordinator if available
    async_add_sensor = getattr(coordinator, "_async_add_entities", None)

    # Create refresh button
    refresh_button = Ship24RefreshButton(coordinator, async_add_sensor)
    async_add_entities([refresh_button])


class Ship24RefreshButton(CoordinatorEntity, ButtonEntity):
    """Button to refresh/update all tracking sensors."""

    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_refresh"
    _attr_name = "Refresh All"

    def __init__(
        self, coordinator: Ship24DataUpdateCoordinator, async_add_sensor_callback
    ) -> None:
        """Initialize the refresh button."""
        super().__init__(coordinator)
        self._async_add_sensor = async_add_sensor_callback

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={DEVICE_IDENTIFIER},
            name=DEVICE_NAME,
            manufacturer="Ship24",
            model="Package Tracking",
        )

    @property
    def icon(self) -> str:
        """Return the icon for the button."""
        return "mdi:refresh"

    async def async_press(self) -> None:
        """Handle the button press - refresh all tracking sensors."""
        _LOGGER.info("Refresh button pressed - updating all tracking sensors")
        
        # Refresh coordinator data
        await self.coordinator.async_request_refresh()
        
        # Check for missing sensors and create them if callback is available
        if self._async_add_sensor:
            tracked_numbers = self.coordinator.get_tracking_numbers()
            entity_registry = er.async_get(self.coordinator.hass)
            
            for tracking_number in tracked_numbers:
                unique_id = f"{DOMAIN}_{tracking_number}"
                entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
                if not entity_id:
                    # Sensor missing, create it
                    _LOGGER.info("Creating missing sensor for %s", tracking_number)
                    # Import here to avoid circular imports
                    from .sensor import Ship24PackageSensor
                    sensor = Ship24PackageSensor(self.coordinator, tracking_number)
                    self._async_add_sensor([sensor])
        
        tracked_count = len(self.coordinator.get_tracking_numbers())
        self.coordinator._last_message = f"Refreshed {tracked_count} tracking sensor{'s' if tracked_count != 1 else ''}"
        self.coordinator._last_error = None
        
        # Trigger coordinator update listeners to update logging sensor
        self.coordinator.async_update_listeners()
        
        self.async_write_ha_state()

