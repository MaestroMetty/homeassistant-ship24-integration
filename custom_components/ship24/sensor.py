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

    @callback
    def async_add_sensor(tracking_number: str) -> None:
        """Add sensor for a tracking number."""
        # Check if sensor already exists
        entity_registry = er.async_get(hass)
        unique_id = f"{DOMAIN}_{tracking_number}"
        if entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id):
            return  # Entity already exists
        
        sensor = Ship24PackageSensor(coordinator, tracking_number)
        async_add_entities([sensor])

    # Add sensors for existing packages
    tracking_numbers = coordinator.get_tracking_numbers()
    if tracking_numbers:
        # Only refresh if we have tracking numbers
        await coordinator.async_config_entry_first_refresh()
        for tracking_number in tracking_numbers:
            async_add_sensor(tracking_number)
    else:
        # No tracking numbers yet - entities will be created when tracking is added via service
        _LOGGER.info("No tracking numbers configured yet. Use ship24.add_tracking service to add packages.")


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
        self._attr_name = None  # Will be set from package data

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        if self.coordinator.data is None:
            # Coordinator data not yet loaded
            return DeviceInfo(
                identifiers={(DOMAIN, self._tracking_number)},
                name=self._tracking_number,
                manufacturer="Ship24",
            )
        
        package = self.coordinator.data.get(self._tracking_number)
        carrier = package.carrier if package else "Unknown Carrier"

        return DeviceInfo(
            identifiers={(DOMAIN, self._tracking_number)},
            name=package.custom_name or self._tracking_number if package else self._tracking_number,
            manufacturer="Ship24",
            model=carrier,
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return "Unknown"
        package = self.coordinator.data.get(self._tracking_number)
        if package:
            return package.status_text or package.status
        return "Unknown"

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
        package = self.coordinator.data.get(self._tracking_number)
        if package:
            # Update name if custom name is set
            self._attr_name = package.custom_name or f"Package {self._tracking_number[:8]}"
        self.async_write_ha_state()

