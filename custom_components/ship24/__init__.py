"""The Ship24 integration."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .app.api import ParcelTrackingAPI
from .const import (
    CONF_API_KEY,
    CONF_WEBHOOK_ID,
    DOMAIN,
    SERVICE_ADD_TRACKING,
    SERVICE_REMOVE_TRACKING,
)
from .coordinator import Ship24DataUpdateCoordinator
from .ship24.adapter import Ship24Adapter, Ship24Backend
from .ship24.client import Ship24Client

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ship24 component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ship24 from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    webhook_id = entry.data.get(CONF_WEBHOOK_ID)

    # Initialize Ship24 layers
    client = Ship24Client(api_key)
    adapter = Ship24Adapter()
    backend = Ship24Backend(client, adapter)
    api = ParcelTrackingAPI(backend)

    # Create coordinator with entry for persistence
    coordinator = Ship24DataUpdateCoordinator(hass, api, entry)

    # Store in hass data
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "client": client,
    }

    # Register webhook if webhook_id is set
    if webhook_id:
        webhook_url = hass.components.webhook.async_generate_url(webhook_id)
        webhook_id_from_api = await api.register_webhook(webhook_url)
        if webhook_id_from_api:
            _LOGGER.info("Registered webhook: %s", webhook_url)
            # Store webhook_id for later use
            hass.data[DOMAIN][entry.entry_id]["webhook_id"] = webhook_id_from_api

    # Register webhook handler
    if webhook_id:
        hass.components.webhook.async_register(
            DOMAIN, f"Ship24 {entry.title}", webhook_id, async_handle_webhook
        )

    # Forward entry setup to platforms (this will call async_setup_entry in sensor.py)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Note: async_config_entry_first_refresh is called in sensor.py after entities are set up

    # Register services
    async def async_add_tracking(call) -> None:
        """Handle add_tracking service call."""
        tracking_number = call.data.get("tracking_number")
        custom_name = call.data.get("custom_name")
        if not tracking_number:
            _LOGGER.error("tracking_number is required")
            return

        success = await coordinator.async_add_tracking(tracking_number, custom_name)
        if success:
            _LOGGER.info("Added tracking: %s", tracking_number)
        else:
            _LOGGER.error("Failed to add tracking: %s", tracking_number)

    async def async_remove_tracking(call) -> None:
        """Handle remove_tracking service call."""
        tracking_number = call.data.get("tracking_number")
        if not tracking_number:
            _LOGGER.error("tracking_number is required")
            return

        success = await coordinator.async_remove_tracking(tracking_number)
        if success:
            _LOGGER.info("Removed tracking: %s", tracking_number)
        else:
            _LOGGER.error("Failed to remove tracking: %s", tracking_number)

    hass.services.async_register(DOMAIN, SERVICE_ADD_TRACKING, async_add_tracking)
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_TRACKING, async_remove_tracking)

    # Initial data fetch will be triggered in sensor.py after entities are set up
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Unregister webhook
        webhook_id = entry.data.get(CONF_WEBHOOK_ID)
        if webhook_id:
            hass.components.webhook.async_unregister(webhook_id)

        # Delete webhook from Ship24
        domain_data = hass.data[DOMAIN].get(entry.entry_id, {})
        api = domain_data.get("api")
        webhook_id_from_api = domain_data.get("webhook_id")
        if api and webhook_id_from_api:
            await api.delete_webhook(webhook_id_from_api)

        # Clean up
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_handle_webhook(
    hass: HomeAssistant, webhook_id: str, request
) -> None:
    """Handle incoming webhook from Ship24."""
    _LOGGER.debug("Received webhook: %s", webhook_id)

    # Find the config entry for this webhook
    entry = None
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if config_entry.data.get(CONF_WEBHOOK_ID) == webhook_id:
            entry = config_entry
            break

    if not entry:
        _LOGGER.warning("No config entry found for webhook: %s", webhook_id)
        return

    # Get coordinator and API
    domain_data = hass.data[DOMAIN].get(entry.entry_id, {})
    coordinator: Ship24DataUpdateCoordinator = domain_data.get("coordinator")
    api: ParcelTrackingAPI = domain_data.get("api")

    if not coordinator or not api:
        _LOGGER.error("Coordinator or API not found for webhook")
        return

    # Parse webhook payload
    try:
        payload = await request.json()
    except Exception as err:
        _LOGGER.error("Failed to parse webhook payload: %s", err)
        return

    # Process webhook via App Layer
    package = await api.process_webhook_payload(payload)
    if package:
        _LOGGER.info("Webhook update received for: %s", package.tracking_number)
        # Trigger coordinator update
        await coordinator.async_request_refresh()
    else:
        _LOGGER.warning("Failed to process webhook payload")

