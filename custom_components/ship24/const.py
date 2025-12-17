"""Constants for the Ship24 integration."""

DOMAIN = "ship24"
INTEGRATION_NAME = "Ship24 Package Tracking"

# Ship24 API Configuration
SHIP24_API_BASE_URL = "https://api.ship24.com/public/v1"
SHIP24_API_TRACKERS_ENDPOINT = "/trackers"
SHIP24_API_TRACKERS_TRACK_ENDPOINT = "/trackers/track"
SHIP24_API_TRACKERS_SEARCH_ENDPOINT = "/trackers/search"
SHIP24_API_WEBHOOKS_ENDPOINT = "/webhooks"

# Config entry keys for storing tracking numbers
CONF_TRACKING_NUMBERS = "tracking_numbers"

# Update intervals
DEFAULT_UPDATE_INTERVAL = 4 * 60 * 60  # 4 hours
WEBHOOK_UPDATE_INTERVAL = 1 * 60 * 60  # 1 hour (fallback polling)

# Entity attributes
ATTR_TRACKING_NUMBER = "tracking_number"
ATTR_CARRIER = "carrier"
ATTR_STATUS = "status"
ATTR_STATUS_TEXT = "status_text"
ATTR_LAST_UPDATE = "last_update"
ATTR_ESTIMATED_DELIVERY = "estimated_delivery"
ATTR_LOCATION = "location"
ATTR_LOCATION_TEXT = "location_text"
ATTR_EVENTS = "events"
ATTR_EVENT_COUNT = "event_count"
ATTR_CUSTOM_NAME = "custom_name"
ATTR_TRACKER_ID = "tracker_id"

# Service names
SERVICE_ADD_TRACKING = "add_tracking"
SERVICE_REMOVE_TRACKING = "remove_tracking"

# Config flow
CONF_API_KEY = "api_key"
CONF_WEBHOOK_ID = "webhook_id"

# Status codes (standardized)
STATUS_PENDING = "pending"
STATUS_IN_TRANSIT = "in_transit"
STATUS_OUT_FOR_DELIVERY = "out_for_delivery"
STATUS_DELIVERED = "delivered"
STATUS_EXCEPTION = "exception"
STATUS_UNKNOWN = "unknown"

