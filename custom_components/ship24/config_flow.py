"""Config flow for Ship24 integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.webhook as webhook

from .const import CONF_API_KEY, CONF_WEBHOOK_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_api_key(hass: HomeAssistant, api_key: str) -> None:
    """Validate the API key by testing connection."""
    # Import here to avoid circular imports
    from .ship24.client import Ship24Client
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        client = Ship24Client(api_key, session)
        is_valid = await client.test_connection()
        if not is_valid:
            raise InvalidApiKey


class InvalidApiKey(HomeAssistantError):
    """Error to indicate the API key is invalid."""


class Ship24ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ship24."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_api_key(self.hass, user_input[CONF_API_KEY])
        except InvalidApiKey:
            errors["base"] = "invalid_api_key"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        # Generate webhook ID
        webhook_id = webhook.async_generate_id()

        return self.async_create_entry(
            title="Ship24 Package Tracking",
            data={
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_WEBHOOK_ID: webhook_id,
            },
        )


