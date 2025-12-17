"""Sensor entities for Ship24 package tracking."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CARRIER,
    ATTR_CUSTOM_NAME,
    ATTR_ESTIMATED_DELIVERY,
    ATTR_EVENT_COUNT,
    ATTR_EVENTS,
    ATTR_LAST_UPDATE,
    ATTR_LOCATION,
    ATTR_LOCATION_TEXT,
    ATTR_STATUS,
    ATTR_STATUS_TEXT,
    ATTR_TRACKER_ID,
    ATTR_TRACKING_NUMBER,
    DEVICE_IDENTIFIER,
    DEVICE_NAME,
    DOMAIN,
    STATUS_DELIVERED,
    STATUS_EXCEPTION,
    STATUS_IN_TRANSIT,
    STATUS_OUT_FOR_DELIVERY,
    STATUS_PENDING,
)
from .coordinator import Ship24DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ship24 sensors from a config entry."""
    coordinator: Ship24DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # Store the async_add_entities callback for dynamic entity creation
    coordinator._async_add_entities = async_add_entities
    coordinator.hass = hass  # Store hass reference for entity removal

    @callback
    def async_add_sensor(tracking_number: str) -> None:
        """Add sensor for a tracking number."""
        # Always create the sensor - Home Assistant will handle deduplication
        # This ensures sensors are recreated during reload even if they exist in registry
        sensor = Ship24PackageSensor(coordinator, tracking_number)
        async_add_entities([sensor])
    
    @callback
    def async_remove_sensor(tracking_number: str) -> None:
        """Remove sensor for a tracking number."""
        entity_registry = er.async_get(hass)
        unique_id = f"{DOMAIN}_{tracking_number}"
        entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id:
            # Remove from entity registry (this will also remove from platform)
            entity_registry.async_remove(entity_id)
            _LOGGER.info("Removed entity %s for tracking number %s", entity_id, tracking_number)
        else:
            _LOGGER.warning("Entity not found in registry for tracking number %s (unique_id: %s)", tracking_number, unique_id)
    
    # Store remove callback
    coordinator._async_remove_entity = async_remove_sensor

    # Create logging sensor (always created)
    logging_sensor = Ship24LoggingSensor(coordinator)
    async_add_entities([logging_sensor])

    # Get tracked numbers and create sensors for all of them
    # This ensures sensors are always created during setup/reload
    tracked_numbers = coordinator.get_tracking_numbers()
    
    # Refresh data FIRST if we have tracking numbers (before creating sensors)
    # This ensures coordinator.data is available when sensors are created
    if tracked_numbers:
        try:
            await coordinator.async_config_entry_first_refresh()
        except Exception as err:
            # Don't fail setup if initial refresh fails (e.g., DNS not ready after reboot)
            # The coordinator will retry automatically
            error_str = str(err).lower()
            if any(keyword in error_str for keyword in ['timeout', 'dns', 'connection', 'network']):
                _LOGGER.warning(
                    "Initial refresh failed due to network issue (likely DNS not ready after reboot): %s. "
                    "Sensors will be created and will retry automatically.",
                    err
                )
            else:
                _LOGGER.error(
                    "Initial refresh failed: %s. Sensors will be created and will retry automatically.",
                    err
                )
    
    if tracked_numbers:
        _LOGGER.info("Creating sensors for %d tracked packages: %s", len(tracked_numbers), tracked_numbers)
        # Create sensors for all tracked numbers
        sensors_to_add = []
        for tracking_number in tracked_numbers:
            sensors_to_add.append(Ship24PackageSensor(coordinator, tracking_number))
        async_add_entities(sensors_to_add)
    else:
        # No tracking numbers yet - entities will be created when tracking is added via service
        _LOGGER.info("No tracking numbers configured yet. Use ship24.add_tracking service to add packages.")
    
    # Check for orphaned sensors (entities in registry but not in tracked list)
    # This handles cleanup of manually removed tracking numbers
    entity_registry = er.async_get(hass)
    existing_entity_ids = []
    for entity_entry in entity_registry.entities.values():
        if entity_entry.platform == DOMAIN and entity_entry.domain == "sensor":
            # Extract tracking number from unique_id (format: ship24_{tracking_number})
            if entity_entry.unique_id.startswith(f"{DOMAIN}_"):
                tracking_num = entity_entry.unique_id.replace(f"{DOMAIN}_", "", 1)
                # Skip logging sensor
                if tracking_num != "logging":
                    existing_entity_ids.append(tracking_num)
    
    # Find orphaned sensors (entity exists but not in tracked list)
    orphaned_sensors = set(existing_entity_ids) - tracked_numbers
    if orphaned_sensors:
        _LOGGER.info("Found %d orphaned sensors, removing them: %s", len(orphaned_sensors), orphaned_sensors)
        for tracking_number in orphaned_sensors:
            async_remove_sensor(tracking_number)


class Ship24PackageSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Ship24 package sensor."""

    _attr_has_entity_name = True
    _attr_state_class = None  # Text-based sensor, not numeric

    def __init__(
        self, coordinator: Ship24DataUpdateCoordinator, tracking_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._tracking_number = tracking_number
        self._attr_unique_id = f"{DOMAIN}_{tracking_number}"
        self._attr_name = tracking_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information - all sensors share the same device."""
        return DeviceInfo(
            identifiers={DEVICE_IDENTIFIER},
            name=DEVICE_NAME,
            manufacturer="Ship24",
            model="Package Tracking",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Entity is available if coordinator has data and this package is in it
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self._tracking_number in self.coordinator.data
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if not self.available:
            return None  # Return None when unavailable (Home Assistant will show "unavailable")
        package = self.coordinator.data.get(self._tracking_number)
        if package:
            return package.status_text or package.status
        return None

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if self.coordinator.data is None:
            return "mdi:package-variant"
        package = self.coordinator.data.get(self._tracking_number)
        if not package:
            return "mdi:package-variant"

        status = package.status
        icon_map = {
            STATUS_PENDING: "mdi:package-variant",
            STATUS_IN_TRANSIT: "mdi:truck-delivery",
            STATUS_OUT_FOR_DELIVERY: "mdi:truck-fast",
            STATUS_DELIVERED: "mdi:check-circle",
            STATUS_EXCEPTION: "mdi:alert-circle",
        }
        return icon_map.get(status, "mdi:package-variant")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.data is None:
            return {}
        package = self.coordinator.data.get(self._tracking_number)
        if not package:
            return {}

        attrs = package.to_dict()
        # Ensure location is properly formatted
        if attrs.get("latitude") and attrs.get("longitude"):
            attrs[ATTR_LOCATION] = {
                "latitude": attrs["latitude"],
                "longitude": attrs["longitude"],
            }
        else:
            attrs[ATTR_LOCATION] = None

        # Remove internal fields
        attrs.pop("latitude", None)
        attrs.pop("longitude", None)

        return {
            ATTR_TRACKING_NUMBER: attrs.get(ATTR_TRACKING_NUMBER),
            ATTR_CARRIER: attrs.get(ATTR_CARRIER),
            ATTR_STATUS: attrs.get(ATTR_STATUS),
            ATTR_STATUS_TEXT: attrs.get(ATTR_STATUS_TEXT),
            ATTR_LAST_UPDATE: attrs.get(ATTR_LAST_UPDATE),
            ATTR_ESTIMATED_DELIVERY: attrs.get(ATTR_ESTIMATED_DELIVERY),
            ATTR_LOCATION: attrs.get(ATTR_LOCATION),
            ATTR_LOCATION_TEXT: attrs.get(ATTR_LOCATION_TEXT),
            ATTR_EVENTS: attrs.get(ATTR_EVENTS),
            ATTR_EVENT_COUNT: attrs.get(ATTR_EVENT_COUNT),
            ATTR_CUSTOM_NAME: attrs.get(ATTR_CUSTOM_NAME),
            ATTR_TRACKER_ID: attrs.get(ATTR_TRACKER_ID),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Ensure name is always set to tracking number
        self._attr_name = self._tracking_number
        self.async_write_ha_state()
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass, write state immediately if data is available."""
        await super().async_added_to_hass()
        # Write state immediately if coordinator already has data
        # This ensures sensors show correct state after reload
        if self.coordinator.data is not None:
            self.async_write_ha_state()


class Ship24LoggingSensor(CoordinatorEntity, SensorEntity):
    """Sensor for displaying last Ship24 message or error."""

    _attr_has_entity_name = True
    _attr_state_class = None
    _attr_unique_id = f"{DOMAIN}_logging"
    _attr_name = "Last Message"

    def __init__(self, coordinator: Ship24DataUpdateCoordinator) -> None:
        """Initialize the logging sensor."""
        super().__init__(coordinator)

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
    def native_value(self) -> str:
        """Return the last message or error."""
        if self.coordinator._last_error:
            return f"Error: {self.coordinator._last_error}"
        if self.coordinator._last_message:
            return self.coordinator._last_message
        return "No messages"

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:message-text" if not self.coordinator._last_error else "mdi:alert-circle"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update when coordinator updates (to reflect new messages/errors)
        self.async_write_ha_state()



