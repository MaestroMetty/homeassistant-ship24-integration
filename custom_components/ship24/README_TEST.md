# Ship24 Integration Test Script

## Overview

The `test_ship24.py` script is a comprehensive test suite for validating the Ship24 integration functionality, API responses, and data formatting.

## Prerequisites

1. Python 3.8 or higher
2. Required packages (install via pip):
   ```bash
   pip install aiohttp
   ```

## Usage

### Basic Usage

Test with API key only (will use first tracker from your Ship24 account):

**Option 1: Run from project root (recommended)**
```bash
cd homeassistant-ship24-integration
python -m custom_components.ship24.test_ship24 YOUR_API_KEY
```

**Option 2: Run directly from test file directory**
```bash
cd custom_components/ship24
python test_ship24.py YOUR_API_KEY
```

### Test with Specific Tracking Number

Test with a specific tracking number:
```bash
# From project root
python -m custom_components.ship24.test_ship24 YOUR_API_KEY S24DEMO456393

# Or from test directory
cd custom_components/ship24
python test_ship24.py YOUR_API_KEY S24DEMO456393
```

## What the Test Does

The test script performs the following checks:

1. **API Connection Test** - Verifies the API key is valid
2. **Get Trackers List** - Retrieves all active trackers (isSubscribed=true, isTracked=true)
3. **Find Tracker** - Searches for a specific tracker in the list
4. **Get Tracker Results** - Fetches full tracking data for a tracking number
5. **Create Tracker** - Tests creating/finding a tracker (handles existing trackers)
6. **Adapter Conversion** - Converts Ship24 API response to PackageData model
7. **Backend Flow** - Tests the complete backend flow (client → adapter → PackageData)
8. **Webhook Payload** - Tests processing webhook payloads

## Output

The script provides detailed output for each test:
- ✓ Success indicators
- ✗ Error indicators
- Formatted JSON responses
- PackageData model details
- Event timelines
- Status mappings

## Example Output

```
================================================================================
  Ship24 Integration Test Suite
================================================================================
API Key: abc1234567...xyz
Tracking Number: S24DEMO456393
Timestamp: 2025-01-15 10:30:45

================================================================================
  Testing API Connection
================================================================================
✓ Connection successful!

================================================================================
  Getting Trackers List
================================================================================
Found 5 active trackers (isSubscribed=true, isTracked=true)
...
```

## Troubleshooting

- **Import Errors**: Make sure you're running from the `custom_components/ship24` directory
- **API Key Invalid**: Verify your API key is correct and has proper permissions
- **No Trackers Found**: Make sure you have active trackers in your Ship24 account
- **Connection Errors**: Check your internet connection and Ship24 API status

## Notes

- The test script does NOT modify your Ship24 account (read-only operations)
- If a tracking number already exists, it will fetch results instead of creating a duplicate
- The webhook test uses sample data and doesn't require actual webhook setup

