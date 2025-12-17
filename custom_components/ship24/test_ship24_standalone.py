#!/usr/bin/env python3
"""Standalone test script for Ship24 integration (no Home Assistant required).

Usage:
    python test_ship24_standalone.py <api_key> [tracking_number]

Examples:
    python test_ship24_standalone.py YOUR_API_KEY
    python test_ship24_standalone.py YOUR_API_KEY S24DEMO456393
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

# Ship24 API Constants (standalone version)
SHIP24_API_BASE_URL = "https://api.ship24.com/public/v1"
SHIP24_API_TRACKERS_ENDPOINT = "/trackers"
SHIP24_API_TRACKERS_TRACK_ENDPOINT = "/trackers/track"
SHIP24_API_TRACKERS_SEARCH_ENDPOINT = "/trackers/search"
SHIP24_API_WEBHOOKS_ENDPOINT = "/webhooks"


# Standalone Ship24Client (no relative imports)
class Ship24Client:
    """Client for interacting with Ship24 API."""

    def __init__(self, api_key: str, session: Optional[aiohttp.ClientSession] = None):
        """Initialize Ship24 client."""
        self._api_key = api_key
        self._session = session
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._base_url = SHIP24_API_BASE_URL

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to Ship24 API."""
        url = f"{self._base_url}{endpoint}"
        session = self._session or aiohttp.ClientSession()

        try:
            async with session.request(
                method, url, headers=self._headers, json=data, params=params
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as err:
            print(f"Ship24 API request failed: {err}")
            raise
        finally:
            if not self._session:
                await session.close()

    async def get_trackers_list(self) -> List[Dict[str, Any]]:
        """Get list of all trackers (only isSubscribed=true and isTracked=true)."""
        try:
            response = await self._request("GET", SHIP24_API_TRACKERS_ENDPOINT)
            trackers = response.get("data", {}).get("trackers", [])
            return [
                t
                for t in trackers
                if t.get("isSubscribed") is True and t.get("isTracked") is True
            ]
        except Exception as err:
            print(f"Failed to get trackers list: {err}")
            return []

    async def find_tracker(self, tracking_number: str) -> Optional[Dict[str, Any]]:
        """Find a tracker by tracking number in the list."""
        trackers = await self.get_trackers_list()
        for tracker in trackers:
            if tracker.get("trackingNumber") == tracking_number:
                return tracker
        return None

    async def create_tracker(
        self, tracking_number: str, carrier_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new tracker or get existing one."""
        existing = await self.find_tracker(tracking_number)
        if existing:
            print(f"Tracker {tracking_number} already exists, fetching results")
            return await self.get_tracker_results(tracking_number)

        data = {"trackingNumber": tracking_number}
        if carrier_code:
            data["courierCode"] = carrier_code

        return await self._request("POST", SHIP24_API_TRACKERS_TRACK_ENDPOINT, data=data)

    async def get_tracker_results(self, tracking_number: str) -> Dict[str, Any]:
        """Get tracker results using search endpoint."""
        endpoint = f"{SHIP24_API_TRACKERS_SEARCH_ENDPOINT}/{tracking_number}/results"
        return await self._request("GET", endpoint)

    async def get_tracker(self, tracking_number: str) -> Dict[str, Any]:
        """Get tracker data (alias for get_tracker_results)."""
        return await self.get_tracker_results(tracking_number)

    async def test_connection(self) -> bool:
        """Test API connection."""
        try:
            await self._request("GET", SHIP24_API_TRACKERS_ENDPOINT, params={"limit": 1})
            return True
        except Exception:
            return False

# Define simplified models for testing (without Home Assistant dependencies)
@dataclass
class TrackingEvent:
    """Represents a single tracking event."""
    timestamp: datetime
    location: Optional[str] = None
    status: Optional[str] = None
    status_text: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PackageData:
    """Standardized package data model."""
    tracking_number: str
    status: str
    status_text: str
    carrier: Optional[str] = None
    carrier_code: Optional[str] = None
    last_update: Optional[datetime] = None
    estimated_delivery: Optional[datetime] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    events: List[TrackingEvent] = field(default_factory=list)
    custom_name: Optional[str] = None
    tracker_id: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tracking_number": self.tracking_number,
            "status": self.status,
            "status_text": self.status_text,
            "carrier": self.carrier,
            "carrier_code": self.carrier_code,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "estimated_delivery": (
                self.estimated_delivery.isoformat() if self.estimated_delivery else None
            ),
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_text": self.location,
            "events": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "location": event.location,
                    "status": event.status,
                    "status_text": event.status_text,
                    "description": event.description,
                    "latitude": event.latitude,
                    "longitude": event.longitude,
                }
                for event in self.events
            ],
            "event_count": len(self.events),
            "custom_name": self.custom_name,
            "tracker_id": self.tracker_id,
        }


# Simplified adapter for testing (no Home Assistant dependencies)
class Ship24AdapterStandalone:
    """Adapter for converting Ship24 API responses to PackageData models."""

    STATUS_PENDING = "pending"
    STATUS_IN_TRANSIT = "in_transit"
    STATUS_OUT_FOR_DELIVERY = "out_for_delivery"
    STATUS_DELIVERED = "delivered"
    STATUS_EXCEPTION = "exception"
    STATUS_UNKNOWN = "unknown"

    @staticmethod
    def _parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Ship24 format."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            try:
                for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
            except Exception:
                pass
            return None

    @staticmethod
    def _map_status_milestone(status_milestone: Optional[str], status_code: Optional[str] = None) -> tuple[str, str]:
        """Map Ship24 statusMilestone to standardized status."""
        if not status_milestone:
            return Ship24AdapterStandalone.STATUS_UNKNOWN, "Unknown"

        milestone_lower = status_milestone.lower()
        status_map = {
            "info_received": (Ship24AdapterStandalone.STATUS_PENDING, "Info Received"),
            "in_transit": (Ship24AdapterStandalone.STATUS_IN_TRANSIT, "In Transit"),
            "out_for_delivery": (Ship24AdapterStandalone.STATUS_OUT_FOR_DELIVERY, "Out for Delivery"),
            "delivered": (Ship24AdapterStandalone.STATUS_DELIVERED, "Delivered"),
            "exception": (Ship24AdapterStandalone.STATUS_EXCEPTION, "Exception"),
            "failed_attempt": (Ship24AdapterStandalone.STATUS_EXCEPTION, "Failed Attempt"),
            "available_for_pickup": (Ship24AdapterStandalone.STATUS_IN_TRANSIT, "Available for Pickup"),
        }

        status_code_result, status_text = status_map.get(milestone_lower, (Ship24AdapterStandalone.STATUS_UNKNOWN, status_milestone))

        if status_code:
            status_code_lower = status_code.lower()
            if "delivery_delivered" in status_code_lower:
                return Ship24AdapterStandalone.STATUS_DELIVERED, "Delivered"
            elif "delivery_out_for_delivery" in status_code_lower:
                return Ship24AdapterStandalone.STATUS_OUT_FOR_DELIVERY, "Out for Delivery"
            elif "exception" in status_code_lower or "failed" in status_code_lower:
                return Ship24AdapterStandalone.STATUS_EXCEPTION, "Exception"

        return status_code_result, status_text

    @staticmethod
    def _parse_events(events_data: List[Dict[str, Any]]) -> List[TrackingEvent]:
        """Parse tracking events from Ship24 response."""
        events = []
        for event_data in events_data or []:
            timestamp = Ship24AdapterStandalone._parse_datetime(
                event_data.get("occurrenceDatetime")
                or event_data.get("occurredAt")
                or event_data.get("datetime")
                or event_data.get("timestamp")
            )
            if not timestamp:
                continue

            status_milestone = event_data.get("statusMilestone")
            status_code = event_data.get("statusCode")
            status_code_result, status_text = Ship24AdapterStandalone._map_status_milestone(
                status_milestone, status_code
            )

            location_text = event_data.get("location")
            event_status_text = event_data.get("status") or status_text

            event = TrackingEvent(
                timestamp=timestamp,
                location=location_text,
                status=status_code_result,
                status_text=event_status_text,
                description=event_status_text,
                latitude=None,
                longitude=None,
                raw_data=event_data,
            )
            events.append(event)

        events.sort(key=lambda e: e.timestamp)
        return events

    @staticmethod
    def to_package_data(tracker_data: Dict[str, Any]) -> PackageData:
        """Convert Ship24 tracker response to PackageData model."""
        data = tracker_data.get("data", {}) or tracker_data
        
        if "trackings" in data and isinstance(data["trackings"], list) and len(data["trackings"]) > 0:
            tracking = data["trackings"][0]
        elif "tracking" in data:
            tracking = data["tracking"]
        else:
            tracking = data

        tracker = tracking.get("tracker", {})
        shipment = tracking.get("shipment", {})
        events_data = tracking.get("events", [])

        tracking_number = tracker.get("trackingNumber")
        if not tracking_number:
            raise ValueError("Missing tracking number in Ship24 response")

        status_milestone = shipment.get("statusMilestone")
        status_code = shipment.get("statusCode")
        status_code_result, status_text = Ship24AdapterStandalone._map_status_milestone(
            status_milestone, status_code
        )

        carrier_code = None
        if events_data:
            latest_event = events_data[0] if events_data else {}
            carrier_code = latest_event.get("courierCode")
        
        courier_codes = tracker.get("courierCode", [])
        if isinstance(courier_codes, list) and courier_codes:
            carrier_code = courier_codes[0]
        elif isinstance(courier_codes, str):
            carrier_code = courier_codes

        events = Ship24AdapterStandalone._parse_events(events_data if isinstance(events_data, list) else [])

        latest_event = events[-1] if events else None
        location = latest_event.location if latest_event else None

        statistics = tracking.get("statistics", {})
        timestamps = statistics.get("timestamps", {}) if statistics else {}
        
        last_update = latest_event.timestamp if latest_event else Ship24AdapterStandalone._parse_datetime(
            timestamps.get("deliveredDatetime")
            or timestamps.get("outForDeliveryDatetime")
            or timestamps.get("inTransitDatetime")
            or timestamps.get("infoReceivedDatetime")
        )
        
        delivery = shipment.get("delivery", {})
        estimated_delivery = Ship24AdapterStandalone._parse_datetime(
            delivery.get("estimatedDeliveryDate")
        )

        tracker_id = tracker.get("trackerId")

        return PackageData(
            tracking_number=tracking_number,
            status=status_code_result,
            status_text=status_text,
            carrier=carrier_code,
            carrier_code=carrier_code,
            last_update=last_update,
            estimated_delivery=estimated_delivery,
            location=location,
            latitude=None,
            longitude=None,
            events=events,
            tracker_id=tracker_id,
            raw_data=tracker_data,
        )


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
        print("✓ Raw API Response received")
        print("\nResponse structure:")
        print(f"  Has 'data' key: {'data' in response}")
        if 'data' in response:
            data = response['data']
            print(f"  Has 'trackings' key: {'trackings' in data}")
            if 'trackings' in data and isinstance(data['trackings'], list):
                print(f"  Number of trackings: {len(data['trackings'])}")
                if len(data['trackings']) > 0:
                    tracking = data['trackings'][0]
                    print(f"  Has 'tracker' key: {'tracker' in tracking}")
                    print(f"  Has 'shipment' key: {'shipment' in tracking}")
                    print(f"  Has 'events' key: {'events' in tracking}")
                    if 'events' in tracking:
                        print(f"  Number of events: {len(tracking['events'])}")
        
        print("\nFull response (first 2000 chars):")
        response_str = json.dumps(response, indent=2, default=str)
        print(response_str[:2000])
        if len(response_str) > 2000:
            print(f"\n... (truncated, total length: {len(response_str)} chars)")
        
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
        print("\nResponse structure:")
        print(f"  Has 'data' key: {'data' in response}")
        if 'data' in response:
            data = response['data']
            print(f"  Has 'trackings' key: {'trackings' in data}")
        
        print("\nFull response (first 2000 chars):")
        response_str = json.dumps(response, indent=2, default=str)
        print(response_str[:2000])
        if len(response_str) > 2000:
            print(f"\n... (truncated, total length: {len(response_str)} chars)")
        
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
        adapter = Ship24AdapterStandalone()
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


async def main():
    """Main test function."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    api_key = sys.argv[1]
    tracking_number = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("\n" + "=" * 80)
    print("  Ship24 Integration Test Suite (Standalone)")
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
            
            # Test 7: Create tracker (will find existing or create new)
            create_response = await test_create_tracker(client, test_tracking_number)
            if create_response:
                await test_adapter_conversion(create_response)
        
        print_section("Test Suite Complete")
        print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())

