"""Data models for package tracking - platform-agnostic."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


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
    """Standardized package data model - platform-agnostic."""

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
        """Convert to dictionary for entity attributes."""
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

