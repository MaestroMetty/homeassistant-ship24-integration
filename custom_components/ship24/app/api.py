"""Platform-agnostic API interface for package tracking."""

from typing import List, Optional

from .models import PackageData


class ParcelTrackingAPI:
    """Platform-agnostic API for package tracking."""

    def __init__(self, backend):
        """Initialize with a backend implementation."""
        self._backend = backend
        self._packages: dict[str, PackageData] = {}

    async def add_tracking(
        self, tracking_number: str, custom_name: Optional[str] = None
    ) -> PackageData:
        """Add a new package to track.

        Args:
            tracking_number: The tracking number to add
            custom_name: Optional custom name for the package

        Returns:
            PackageData object for the tracked package
        """
        # Create tracker via backend
        package_data = await self._backend.create_tracker(tracking_number)
        
        # Set custom name if provided
        if custom_name:
            package_data.custom_name = custom_name
        
        # Store package data
        self._packages[tracking_number] = package_data
        
        return package_data

    async def get_package(self, tracking_number: str) -> Optional[PackageData]:
        """Get package data for a tracking number.

        Args:
            tracking_number: The tracking number to retrieve

        Returns:
            PackageData object or None if not found
        """
        # Check cache first
        if tracking_number in self._packages:
            return self._packages[tracking_number]
        
        # Fetch from backend
        package_data = await self._backend.get_tracker(tracking_number)
        if package_data:
            self._packages[tracking_number] = package_data
        
        return package_data

    async def get_all_packages(self) -> List[PackageData]:
        """Get all tracked packages.

        Returns:
            List of PackageData objects
        """
        # Refresh all packages from backend
        packages = []
        for tracking_number in list(self._packages.keys()):
            package = await self.get_package(tracking_number)
            if package:
                packages.append(package)
        
        return packages

    async def remove_tracking(self, tracking_number: str) -> bool:
        """Remove a package from tracking.

        Note: This only removes from Home Assistant tracking, not from Ship24.
        The package remains in Ship24 but is no longer tracked in HA.

        Args:
            tracking_number: The tracking number to remove

        Returns:
            True if removed, False if not found
        """
        if tracking_number in self._packages:
            # Don't delete from Ship24, just remove from our tracking
            del self._packages[tracking_number]
            return True
        return False

    async def update_package(self, tracking_number: str) -> Optional[PackageData]:
        """Refresh package data from backend.

        Args:
            tracking_number: The tracking number to update

        Returns:
            Updated PackageData object or None if not found
        """
        package_data = await self._backend.get_tracker(tracking_number)
        if package_data:
            # Preserve custom name if it exists
            if tracking_number in self._packages:
                package_data.custom_name = self._packages[tracking_number].custom_name
            self._packages[tracking_number] = package_data
        return package_data

    async def register_webhook(self, webhook_url: str) -> Optional[str]:
        """Register a webhook URL for real-time updates.

        Args:
            webhook_url: The webhook URL to register

        Returns:
            Webhook ID if successful, None otherwise
        """
        return await self._backend.register_webhook(webhook_url)

    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook.

        Args:
            webhook_id: The webhook ID to delete

        Returns:
            True if deleted, False otherwise
        """
        return await self._backend.delete_webhook(webhook_id)

    async def process_webhook_payload(self, payload: dict) -> Optional[PackageData]:
        """Process incoming webhook payload.

        Args:
            payload: The webhook payload from the backend

        Returns:
            Updated PackageData object or None
        """
        # Let backend adapter process the payload
        package_data = await self._backend.process_webhook(payload)
        if package_data:
            # Preserve custom name if it exists
            if package_data.tracking_number in self._packages:
                package_data.custom_name = (
                    self._packages[package_data.tracking_number].custom_name
                )
            self._packages[package_data.tracking_number] = package_data
        return package_data

    def set_custom_name(self, tracking_number: str, custom_name: Optional[str]) -> bool:
        """Set or update custom name for a package.

        Args:
            tracking_number: The tracking number
            custom_name: The custom name (None to remove)

        Returns:
            True if package exists, False otherwise
        """
        if tracking_number in self._packages:
            self._packages[tracking_number].custom_name = custom_name
            return True
        return False

