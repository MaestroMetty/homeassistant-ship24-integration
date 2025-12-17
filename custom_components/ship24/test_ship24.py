#!/usr/bin/env python3
"""Test script for Ship24 integration.

Usage:
    python test_ship24.py <api_key> [tracking_number]

Examples:
    python test_ship24.py YOUR_API_KEY
    python test_ship24.py YOUR_API_KEY S24DEMO456393
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Optional

import aiohttp

# Import our modules
# Add parent directories to path for imports

# Get the directory containing this script (custom_components/ship24)
script_dir = os.path.dirname(os.path.abspath(__file__))
# Get the custom_components directory (parent of script_dir)
custom_components_dir = os.path.dirname(script_dir)
# Get the project root (parent of custom_components_dir)  
project_root = os.path.dirname(custom_components_dir)

# Add project root to sys.path so we can import our modules
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import using the full path from project root
try:
    from custom_components.ship24.ship24.adapter import Ship24Adapter, Ship24Backend
    from custom_components.ship24.ship24.client import Ship24Client
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Script dir: {script_dir}")
    print(f"Custom components dir: {custom_components_dir}")
    print(f"Project root: {project_root}")
    print(f"Python path: {sys.path}")
    sys.exit(1)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_json(data: dict, indent: int = 2):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=indent, default=str))


async def test_connection(client: Ship24Client) -> bool:
    """Test API connection."""
    print_section("Testing API Connection")
    try:
        result = await client.test_connection()
        if result:
            print("✓ Connection successful!")
        else:
            print("✗ Connection failed!")
        return result
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False


async def test_get_trackers_list(client: Ship24Client):
    """Test getting list of trackers."""
    print_section("Getting Trackers List")
    try:
        trackers = await client.get_trackers_list()
        print(f"Found {len(trackers)} active trackers (isSubscribed=true, isTracked=true)")
        
        if trackers:
            print("\nFirst 5 trackers:")
            for i, tracker in enumerate(trackers[:5], 1):
                print(f"\n{i}. Tracking Number: {tracker.get('trackingNumber')}")
                print(f"   Tracker ID: {tracker.get('trackerId')}")
                print(f"   Is Subscribed: {tracker.get('isSubscribed')}")
                print(f"   Is Tracked: {tracker.get('isTracked')}")
                print(f"   Created At: {tracker.get('createdAt')}")
        else:
            print("No active trackers found.")
        
        return trackers
    except Exception as e:
        print(f"✗ Error getting trackers list: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_find_tracker(client: Ship24Client, tracking_number: str):
    """Test finding a specific tracker."""
    print_section(f"Finding Tracker: {tracking_number}")
    try:
        tracker = await client.find_tracker(tracking_number)
        if tracker:
            print("✓ Tracker found!")
            print(f"  Tracker ID: {tracker.get('trackerId')}")
            print(f"  Tracking Number: {tracker.get('trackingNumber')}")
            print(f"  Is Subscribed: {tracker.get('isSubscribed')}")
            print(f"  Is Tracked: {tracker.get('isTracked')}")
            return tracker
        else:
            print(f"✗ Tracker {tracking_number} not found in active trackers")
            return None
    except Exception as e:
        print(f"✗ Error finding tracker: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_get_tracker_results(client: Ship24Client, tracking_number: str):
    """Test getting tracker results."""
    print_section(f"Getting Tracker Results: {tracking_number}")
    try:
        response = await client.get_tracker_results(tracking_number)
        print("✓ Raw API Response:")
        print_json(response)
        return response
    except Exception as e:
        print(f"✗ Error getting tracker results: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_create_tracker(client: Ship24Client, tracking_number: str):
    """Test creating a new tracker."""
    print_section(f"Creating Tracker: {tracking_number}")
    try:
        response = await client.create_tracker(tracking_number)
        print("✓ Tracker created/found!")
        print("\nRaw API Response:")
        print_json(response)
        return response
    except Exception as e:
        print(f"✗ Error creating tracker: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_adapter_conversion(tracker_data: dict):
    """Test converting Ship24 response to PackageData."""
    print_section("Testing Adapter Conversion")
    try:
        adapter = Ship24Adapter()
        package_data = adapter.to_package_data(tracker_data)
        
        print("✓ Conversion successful!")
        print("\nPackageData Model:")
        print(f"  Tracking Number: {package_data.tracking_number}")
        print(f"  Status: {package_data.status}")
        print(f"  Status Text: {package_data.status_text}")
        print(f"  Carrier: {package_data.carrier}")
        print(f"  Carrier Code: {package_data.carrier_code}")
        print(f"  Tracker ID: {package_data.tracker_id}")
        print(f"  Last Update: {package_data.last_update}")
        print(f"  Estimated Delivery: {package_data.estimated_delivery}")
        print(f"  Location: {package_data.location}")
        print(f"  Latitude: {package_data.latitude}")
        print(f"  Longitude: {package_data.longitude}")
        print(f"  Event Count: {len(package_data.events)}")
        
        if package_data.events:
            print("\n  Recent Events (last 3):")
            for i, event in enumerate(package_data.events[-3:], 1):
                print(f"    {i}. {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"       Status: {event.status_text}")
                print(f"       Location: {event.location or 'N/A'}")
        
        print("\n  PackageData as Dictionary:")
        package_dict = package_data.to_dict()
        print_json(package_dict)
        
        return package_data
    except Exception as e:
        print(f"✗ Error converting data: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_backend_flow(client: Ship24Client, tracking_number: str):
    """Test the full backend flow."""
    print_section("Testing Full Backend Flow")
    try:
        adapter = Ship24Adapter()
        backend = Ship24Backend(client, adapter)
        
        print(f"Creating/getting tracker: {tracking_number}")
        package_data = await backend.create_tracker(tracking_number)
        
        if package_data:
            print("✓ Backend flow successful!")
            print(f"  Tracking Number: {package_data.tracking_number}")
            print(f"  Status: {package_data.status_text}")
            print(f"  Events: {len(package_data.events)}")
        else:
            print("✗ Backend flow failed!")
        
        return package_data
    except Exception as e:
        print(f"✗ Error in backend flow: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_webhook_payload():
    """Test webhook payload processing."""
    print_section("Testing Webhook Payload Processing")
    
    # Sample webhook payload based on Ship24 documentation
    webhook_payload = {
        "trackings": [
            {
                "metadata": {
                    "generatedAt": "2025-03-04T17:13:35.000Z",
                    "messageId": "356a7f93-3ce5-4b49-b560-156537283df9"
                },
                "tracker": {
                    "trackerId": "26148317-7502-d3ac-44a9-546d240ac0dd",
                    "trackingNumber": "S24DEMO456393",
                    "shipmentReference": "c6e4fef4-a816-b68f-4024-3b7e4c5a9f81",
                    "clientTrackerId": "3fa99515-3ca0-4901-85bb-056ee016799b",
                    "isSubscribed": True,
                    "createdAt": "2025-03-01T03:16:22.000Z"
                },
                "shipment": {
                    "shipmentId": "f4f888d7-d140-423f-9a48-e0689d27e098",
                    "statusCode": "delivery_delivered",
                    "statusCategory": "delivery",
                    "statusMilestone": "delivered",
                    "originCountryCode": "US",
                    "destinationCountryCode": "CN",
                    "delivery": {
                        "estimatedDeliveryDate": None,
                        "service": None,
                        "signedBy": None
                    },
                    "trackingNumbers": [
                        {"tn": "S24DEMO456393"},
                        {"tn": "S24DEMO169411"}
                    ],
                    "recipient": {
                        "name": None,
                        "address": None,
                        "postCode": "94901",
                        "city": None,
                        "subdivision": None
                    }
                },
                "events": [
                    {
                        "eventId": "ee8ebe96-4eae-4a91-9a99-8f3afa6a0f46",
                        "trackingNumber": "S24DEMO169411",
                        "eventTrackingNumber": "S24DEMO169411",
                        "status": "Delivered to the addressee",
                        "occurrenceDatetime": "2025-03-04T17:12:57",
                        "order": None,
                        "location": "SAN RAFAEL, CA 94901",
                        "sourceCode": "usps-tracking",
                        "courierCode": "us-post",
                        "statusCode": "delivery_delivered",
                        "statusCategory": "delivery",
                        "statusMilestone": "delivered",
                        "hasNoTime": "false,",
                        "utcOffset": "null,",
                        "datetime": "2025-03-04T17:12:57.000Z"
                    }
                ],
                "statistics": {
                    "timestamps": {
                        "infoReceivedDatetime": "2025-03-02T15:38:57",
                        "inTransitDatetime": "2025-03-02T15:38:57",
                        "outForDeliveryDatetime": "2025-03-04T10:12:57",
                        "failedAttemptDatetime": None,
                        "availableForPickupDatetime": None,
                        "exceptionDatetime": None,
                        "deliveredDatetime": "2025-03-04T17:12:57"
                    }
                }
            }
        ]
    }
    
    try:
        adapter = Ship24Adapter()
        package_data = await adapter.process_webhook(webhook_payload)
        
        if package_data:
            print("✓ Webhook payload processed successfully!")
            print(f"  Tracking Number: {package_data.tracking_number}")
            print(f"  Status: {package_data.status_text}")
            print(f"  Events: {len(package_data.events)}")
            print("\n  PackageData Dictionary:")
            print_json(package_data.to_dict())
        else:
            print("✗ Failed to process webhook payload!")
        
        return package_data
    except Exception as e:
        print(f"✗ Error processing webhook: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Main test function."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    api_key = sys.argv[1]
    tracking_number = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("\n" + "=" * 80)
    print("  Ship24 Integration Test Suite")
    print("=" * 80)
    print(f"API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")
    if tracking_number:
        print(f"Tracking Number: {tracking_number}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create client
    async with aiohttp.ClientSession() as session:
        client = Ship24Client(api_key, session)
        
        # Test 1: Connection
        if not await test_connection(client):
            print("\n✗ Connection test failed. Exiting.")
            return
        
        # Test 2: Get trackers list
        trackers = await test_get_trackers_list(client)
        
        # Test 3: Find tracker (if tracking number provided or use first from list)
        test_tracking_number = tracking_number
        if not test_tracking_number and trackers:
            test_tracking_number = trackers[0].get("trackingNumber")
            print(f"\nUsing tracking number from list: {test_tracking_number}")
        
        if test_tracking_number:
            # Test 4: Find tracker
            await test_find_tracker(client, test_tracking_number)
            
            # Test 5: Get tracker results
            tracker_results = await test_get_tracker_results(client, test_tracking_number)
            
            if tracker_results:
                # Test 6: Adapter conversion
                package_data = await test_adapter_conversion(tracker_results)
                
                if package_data:
                    # Test 7: Backend flow
                    await test_backend_flow(client, test_tracking_number)
        
        # Test 8: Webhook payload processing
        await test_webhook_payload()
        
        print_section("Test Suite Complete")
        print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())

