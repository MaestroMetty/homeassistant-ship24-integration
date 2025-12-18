"""The Ship24 integration."""

import logging
from typing import Any

from aiohttp import web

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

# Import webhook components
try:
    from homeassistant.components.webhook import async_register, async_unregister
    WEBHOOK_AVAILABLE = True
except ImportError:
    async_register = None
    async_unregister = None
    WEBHOOK_AVAILABLE = False
    _LOGGER.warning("Webhook component not available - webhook functionality will be disabled")

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

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

# Config schema - this integration only uses config flow
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


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

    # Register webhook handler if webhook_id is available
    if webhook_id and WEBHOOK_AVAILABLE:
        try:
            async_register(
                hass,
                domain=DOMAIN,
                name=f"Ship24 {entry.title}",
                webhook_id=webhook_id,
                handler=async_handle_webhook,
            )
            _LOGGER.info("Registered webhook handler with ID: %s", webhook_id)
            
            # Automatically register webhook URL with Ship24 API
            try:
                webhook_url = await client.get_webhook_url(webhook_id)
                if webhook_url:
                    # Check if URL appears to be internal (private IP ranges)
                    is_internal = False
                    if webhook_base_url.startswith("http://172.") or webhook_base_url.startswith("http://192.168.") or webhook_base_url.startswith("http://10.") or webhook_base_url.startswith("http://127.") or webhook_base_url.startswith("http://169.254."):
                        is_internal = True
                    
                    if is_internal:
                        _LOGGER.warning(
                            "Webhook URL appears to be an internal IP address: %s\n"
                            "Ship24's servers cannot reach internal IPs from the internet.\n"
                            "Please configure an external URL in Home Assistant settings:\n"
                            "  Settings > System > Network > External URL",
                            webhook_full_url
                        )
                    else:
                        # Automatically register webhook with Ship24 API
                        _LOGGER.info("Registering webhook URL with Ship24 API: %s", webhook_full_url)
                        registered_webhook_id = await api.register_webhook(webhook_full_url)
                        if registered_webhook_id:
                            _LOGGER.info(
                                "Successfully registered webhook with Ship24 API. Webhook ID: %s",
                                registered_webhook_id
                            )
                        else:
                            _LOGGER.warning(
                                "Failed to register webhook with Ship24 API. "
                                "The webhook handler is registered locally, but Ship24 may not be able to send updates."
                            )
                else:
                    _LOGGER.warning(
                        "No external URL configured. Cannot register webhook with Ship24 API.\n"
                        "Please set up an external URL in: Settings > System > Network > External URL"
                    )
            except Exception as err:
                _LOGGER.error(
                    "Failed to register webhook with Ship24 API: %s\n"
                    "The webhook handler is registered locally, but automatic registration with Ship24 failed.",
                    err
                )
        except ValueError as err:
            # ValueError is raised when webhook is already registered
            if "already defined" in str(err).lower() or "already registered" in str(err).lower():
                _LOGGER.debug("Webhook %s is already registered, skipping", webhook_id)
            else:
                _LOGGER.error("Failed to register webhook handler: %s", err)
        except Exception as err:
            _LOGGER.error("Failed to register webhook handler: %s", err)
    elif webhook_id and not WEBHOOK_AVAILABLE:
        _LOGGER.warning("Webhook ID provided but webhook component is not available")

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
        
        if webhook_id and WEBHOOK_AVAILABLE:
            try:
                async_unregister(hass, webhook_id)
            except Exception as err:
                _LOGGER.warning("Failed to unregister webhook: %s", err)

        # Clean up
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: web.Request
) -> web.Response:
    """Handle incoming webhook from Ship24.
    
    This handler receives POST requests from Ship24 when package tracking updates occur.
    The webhook_id matches the ID registered during setup.
    """
    _LOGGER.info(
        "Webhook handler called with ID: %s | Method: %s | Path: %s | Headers: %s",
        webhook_id,
        request.method,
        request.path,
        dict(request.headers)
    )
    try:
        _LOGGER.debug("Received webhook: %s", webhook_id)

        # Find the config entry for this webhook
        entry = None
        registered_ids = []
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            stored_webhook_id = config_entry.data.get(CONF_WEBHOOK_ID)
            if stored_webhook_id:
                registered_ids.append(stored_webhook_id)
            if stored_webhook_id == webhook_id:
                entry = config_entry
                _LOGGER.info("Found matching config entry for webhook ID: %s", webhook_id)
                break

        if registered_ids:
            _LOGGER.debug("Registered webhook IDs: %s", registered_ids)

        if not entry:
            _LOGGER.warning("No config entry found for webhook ID: %s. Registered IDs: %s", webhook_id, registered_ids)
            return web.Response(status=404, text="Webhook not found")

        # Get coordinator and API
        domain_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        coordinator: Ship24DataUpdateCoordinator = domain_data.get("coordinator")
        api: ParcelTrackingAPI = domain_data.get("api")

        if not coordinator or not api:
            _LOGGER.error("Coordinator or API not found for webhook")
            return web.Response(status=500, text="Internal server error")

        # Parse webhook payload
        try:
            payload = await request.json()
            _LOGGER.info("Webhook payload received: %s", payload)
        except Exception as err:
            _LOGGER.error("Failed to parse webhook payload: %s", err)
            # Try to read raw body for debugging
            try:
                body = await request.text()
                _LOGGER.debug("Raw webhook body: %s", body)
            except Exception:
                pass
            return web.Response(status=400, text="Invalid payload")

        # Process webhook via App Layer
        try:
            _LOGGER.info("Processing webhook payload via API layer")
            package = await api.process_webhook_payload(payload)
            if package:
                tracking_number = package.tracking_number
                _LOGGER.info("Webhook processed successfully. Package tracking number: %s", tracking_number)
                
                # Only process webhook if this tracking number is being tracked in Home Assistant
                tracked_numbers = coordinator.get_tracking_numbers()
                _LOGGER.debug("Currently tracked packages: %s", tracked_numbers)
                if tracking_number not in tracked_numbers:
                    _LOGGER.info(
                        "Webhook received for untracked package %s. Ignoring (not tracked in Home Assistant).",
                        tracking_number
                    )
                    return web.Response(status=200, text="OK")  # Return OK to avoid retries
                
                _LOGGER.info("Webhook update received for tracked package: %s. Triggering refresh.", tracking_number)
                # Trigger coordinator update to refresh the package
                await coordinator.async_request_refresh()
                _LOGGER.info("Coordinator refresh triggered successfully")
                return web.Response(status=200, text="OK")
            else:
                _LOGGER.warning("Failed to process webhook payload - package is None")
                return web.Response(status=200, text="OK")  # Return OK even if processing failed to avoid retries
        except Exception as err:
            _LOGGER.exception("Error processing webhook payload: %s", err)
            return web.Response(status=500, text="Error processing webhook")
    except Exception as err:
        _LOGGER.exception("Unexpected error in webhook handler: %s", err)
        return web.Response(status=500, text="Internal server error")

