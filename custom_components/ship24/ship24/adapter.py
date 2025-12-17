"""Ship24 response adapter - Converts Ship24 API responses to PackageData models."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..app.models import PackageData, TrackingEvent
from ..const import (
    STATUS_DELIVERED,
    STATUS_EXCEPTION,
    STATUS_IN_TRANSIT,
    STATUS_OUT_FOR_DELIVERY,
    STATUS_PENDING,
    STATUS_UNKNOWN,
)

if TYPE_CHECKING:
    from .client import Ship24Client

_LOGGER = logging.getLogger(__name__)


class Ship24Adapter:
    """Adapter for converting Ship24 API responses to PackageData models."""

    @staticmethod
    def _parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Ship24 format."""
        if not date_str:
            return None
        try:
            # Ship24 uses ISO format, try parsing
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            try:
                # Try alternative formats
                for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
            except Exception:
                pass
            _LOGGER.warning("Failed to parse datetime: %s", date_str)
            return None

    @staticmethod
    def _map_status_milestone(status_milestone: Optional[str], status_code: Optional[str] = None) -> tuple[str, str]:
        """Map Ship24 statusMilestone to standardized status.

        Args:
            status_milestone: The statusMilestone from Ship24
            status_code: Optional statusCode for additional context

        Returns:
            Tuple of (status_code, status_text)
        """
        if not status_milestone:
            return STATUS_UNKNOWN, "Unknown"

        milestone_lower = status_milestone.lower()

        # Map Ship24 statusMilestone values
        status_map = {
            "info_received": (STATUS_PENDING, "Info Received"),
            "in_transit": (STATUS_IN_TRANSIT, "In Transit"),
            "out_for_delivery": (STATUS_OUT_FOR_DELIVERY, "Out for Delivery"),
            "delivered": (STATUS_DELIVERED, "Delivered"),
            "exception": (STATUS_EXCEPTION, "Exception"),
            "failed_attempt": (STATUS_EXCEPTION, "Failed Attempt"),
            "available_for_pickup": (STATUS_IN_TRANSIT, "Available for Pickup"),
        }

        status_code_result, status_text = status_map.get(milestone_lower, (STATUS_UNKNOWN, status_milestone))

        # Override with statusCode if it provides more specific info
        if status_code:
            status_code_lower = status_code.lower()
            if "delivery_delivered" in status_code_lower:
                return STATUS_DELIVERED, "Delivered"
            elif "delivery_out_for_delivery" in status_code_lower:
                return STATUS_OUT_FOR_DELIVERY, "Out for Delivery"
            elif "exception" in status_code_lower or "failed" in status_code_lower:
                return STATUS_EXCEPTION, "Exception"

        return status_code_result, status_text

    @staticmethod
    def _extract_location(event: Dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[str]]:
        """Extract location data from event.

        Returns:
            Tuple of (latitude, longitude, location_text)
        """
        location = event.get("location") or {}
        if isinstance(location, dict):
            lat = location.get("latitude") or location.get("lat")
            lng = location.get("longitude") or location.get("lng") or location.get("lon")
            location_text = location.get("address") or location.get("name") or location.get("city")
            try:
                lat_float = float(lat) if lat is not None else None
                lng_float = float(lng) if lng is not None else None
                return lat_float, lng_float, location_text
            except (ValueError, TypeError):
                pass
        elif isinstance(location, str):
            return None, None, location

        return None, None, None

    @staticmethod
    def _parse_events(events_data: List[Dict[str, Any]]) -> List[TrackingEvent]:
        """Parse tracking events from Ship24 response."""
        events = []
        for event_data in events_data or []:
            # Ship24 uses occurrenceDatetime
            timestamp = Ship24Adapter._parse_datetime(
                event_data.get("occurrenceDatetime")
                or event_data.get("occurredAt")
                or event_data.get("datetime")
                or event_data.get("timestamp")
            )
            if not timestamp:
                continue

            # Use statusMilestone for status mapping
            status_milestone = event_data.get("statusMilestone")
            status_code = event_data.get("statusCode")
            status_code_result, status_text = Ship24Adapter._map_status_milestone(
                status_milestone, status_code
            )

            # Location is a string in Ship24 events
            location_text = event_data.get("location")
            lat, lng = None, None  # Ship24 events don't have lat/lng in location field

            # Status text from event
            event_status_text = event_data.get("status") or status_text

            event = TrackingEvent(
                timestamp=timestamp,
                location=location_text,
                status=status_code_result,
                status_text=event_status_text,
                description=event_status_text,
                latitude=lat,
                longitude=lng,
                raw_data=event_data,
            )
            events.append(event)

        # Sort by timestamp (oldest first)
        events.sort(key=lambda e: e.timestamp)
        return events

    @staticmethod
    def to_package_data(tracker_data: Dict[str, Any]) -> PackageData:
        """Convert Ship24 tracker response to PackageData model.

        Args:
            tracker_data: Raw Ship24 API response (from /trackers/track or /trackers/search/{tn}/results)

        Returns:
            PackageData model
        """
        # Handle response structure: data.trackings[0] or direct tracking object
        data = tracker_data.get("data", {}) or tracker_data
        
        # Get tracking object - can be in trackings array or directly in data
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

        # Get status from shipment.statusMilestone
        status_milestone = shipment.get("statusMilestone")
        status_code = shipment.get("statusCode")
        status_code_result, status_text = Ship24Adapter._map_status_milestone(
            status_milestone, status_code
        )

        # Get carrier info from events (courierCode in events)
        carrier_code = None
        if events_data:
            # Get most recent event's courier
            latest_event = events_data[0] if events_data else {}
            carrier_code = latest_event.get("courierCode")
        
        # Try to get carrier name from tracker if available
        courier_codes = tracker.get("courierCode", [])
        if isinstance(courier_codes, list) and courier_codes:
            carrier_code = carrier_codes[0]
        elif isinstance(courier_codes, str):
            carrier_code = courier_codes

        # Parse events
        events = Ship24Adapter._parse_events(events_data if isinstance(events_data, list) else [])

        # Get latest event for location
        latest_event = events[-1] if events else None
        location = latest_event.location if latest_event else None
        latitude = latest_event.latitude if latest_event else None
        longitude = latest_event.longitude if latest_event else None

        # Get timestamps from statistics or events
        statistics = tracking.get("statistics", {})
        timestamps = statistics.get("timestamps", {}) if statistics else {}
        
        last_update = latest_event.timestamp if latest_event else Ship24Adapter._parse_datetime(
            timestamps.get("deliveredDatetime")
            or timestamps.get("outForDeliveryDatetime")
            or timestamps.get("inTransitDatetime")
            or timestamps.get("infoReceivedDatetime")
        )
        
        # Estimated delivery from shipment.delivery
        delivery = shipment.get("delivery", {})
        estimated_delivery = Ship24Adapter._parse_datetime(
            delivery.get("estimatedDeliveryDate")
        )

        # Get tracker ID
        tracker_id = tracker.get("trackerId")

        return PackageData(
            tracking_number=tracking_number,
            status=status_code_result,
            status_text=status_text,
            carrier=carrier_code,  # Use code as carrier name for now
            carrier_code=carrier_code,
            last_update=last_update,
            estimated_delivery=estimated_delivery,
            location=location,
            latitude=latitude,
            longitude=longitude,
            events=events,
            tracker_id=tracker_id,
            raw_data=tracker_data,
        )

    @staticmethod
    async def process_webhook(webhook_payload: Dict[str, Any]) -> Optional[PackageData]:
        """Process webhook payload from Ship24.

        Args:
            webhook_payload: Raw webhook payload (has trackings array)

        Returns:
            PackageData model or None if invalid
        """
        try:
            # Webhook has trackings array
            trackings = webhook_payload.get("trackings", [])
            if not trackings or len(trackings) == 0:
                _LOGGER.warning("Webhook payload has no trackings")
                return None

            # Process first tracking (webhooks usually send one at a time)
            tracking = trackings[0]
            
            # Convert to same format as API response
            tracker_data = {"data": {"trackings": [tracking]}}
            return Ship24Adapter.to_package_data(tracker_data)
        except Exception as err:
            _LOGGER.error("Failed to process webhook payload: %s", err)
            return None


class Ship24Backend:
    """Backend implementation that App Layer uses."""

    def __init__(self, client, adapter: Ship24Adapter):
        """Initialize backend with client and adapter.
        
        Args:
            client: Ship24Client instance
            adapter: Ship24Adapter instance
        """
        self._client = client
        self._adapter = adapter

    async def create_tracker(self, tracking_number: str) -> PackageData:
        """Create tracker and return PackageData."""
        response = await self._client.create_tracker(tracking_number)
        return self._adapter.to_package_data(response)

    async def get_tracker(self, tracking_number: str) -> Optional[PackageData]:
        """Get tracker and return PackageData."""
        try:
            response = await self._client.get_tracker(tracking_number)
            return self._adapter.to_package_data(response)
        except Exception as err:
            _LOGGER.error("Failed to get tracker %s: %s", tracking_number, err)
            return None

    async def delete_tracker(self, tracking_number: str) -> bool:
        """Delete tracker."""
        return await self._client.delete_tracker(tracking_number)

    async def register_webhook(self, webhook_url: str) -> Optional[str]:
        """Register webhook."""
        return await self._client.register_webhook(webhook_url)

    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete webhook."""
        return await self._client.delete_webhook(webhook_id)

    async def process_webhook(self, payload: dict) -> Optional[PackageData]:
        """Process webhook payload."""
        return self._adapter.process_webhook(payload)

