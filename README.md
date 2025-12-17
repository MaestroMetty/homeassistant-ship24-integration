# Ship24 Package Tracking Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

A Home Assistant integration for tracking packages using the Ship24 API. This integration provides sensor entities for each tracked package with detailed tracking information, status updates, and location data.

## Features

- Track multiple packages simultaneously
- Real-time updates via webhooks (with polling fallback)
- Detailed tracking information including:
  - Current status and location
  - Complete event timeline
  - Estimated delivery dates
  - Carrier information
- Custom names for packages
- Automatic status updates

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to Integrations
3. Click the three dots in the top right
4. Select "Custom repositories"
5. Add this repository URL
6. Click "Install"

### Manual Installation

1. Copy the `custom_components/ship24` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services → Add Integration

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Ship24"
4. Enter your Ship24 API key
5. Follow the setup wizard

## Usage

After configuration, sensor entities will be created for each tracked package. You can:

- View package status in the Home Assistant UI
- Use package data in automations
- Track packages via the companion custom card (separate repository)

## Services

### `ship24.add_tracking`

Add a new package to track.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tracking_number` | string | Yes | The tracking number to add |
| `custom_name` | string | No | Custom name for the package |

### `ship24.remove_tracking`

Remove a package from tracking.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tracking_number` | string | Yes | The tracking number to remove |

## Entity Attributes

Each package sensor includes the following attributes:

- `tracking_number`: The tracking number
- `carrier`: Carrier name/code
- `status`: Current status code
- `status_text`: Human-readable status
- `last_update`: Timestamp of last update
- `estimated_delivery`: Estimated delivery date
- `location`: Location coordinates (lat/lng)
- `location_text`: Human-readable location
- `events`: JSON array of all tracking events
- `event_count`: Total number of events
- `custom_name`: User-defined name
- `tracker_id`: Ship24 tracker ID

## Requirements

- Home Assistant 2024.1.0 or later
- Ship24 API key (get one at [ship24.com](https://ship24.com))

## Support

For issues, feature requests, or questions, please open an issue on [GitHub](https://github.com/yourusername/homeassistant-ship24-integration/issues).

## License

MIT License

