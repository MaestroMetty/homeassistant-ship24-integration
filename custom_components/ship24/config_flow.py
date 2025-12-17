"""Config flow for Ship24 integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_API_KEY, CONF_WEBHOOK_ID, DOMAIN
from .ship24.adapter import Ship24Adapter
from .ship24.client import Ship24Client

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_api_key(hass: HomeAssistant, api_key: str) -> None:
    """Validate the API key by testing connection."""
    client = Ship24Client(api_key)
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
        webhook_id = self.hass.components.webhook.async_generate_id()

        return self.async_create_entry(
            title="Ship24 Package Tracking",
            data={
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_WEBHOOK_ID: webhook_id,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return Ship24OptionsFlowHandler(config_entry)


class Ship24OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Ship24."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    # Add any options here in the future
                }
            ),
        )

