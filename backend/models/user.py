"""
User model for MeshNetwork application.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import uuid


class User:
    """User data model."""

    def __init__(
        self,
        user_id: Optional[str] = None,
        name: str = "",
        email: str = "",
        region: str = "",
        location: Optional[Dict[str, Any]] = None,
        verified: bool = False,
        reputation: int = 0,
        created_at: Optional[datetime] = None
    ):
        self.user_id = user_id or str(uuid.uuid4())
        self.name = name
        self.email = email
        self.region = region
        self.location = location or {"type": "Point", "coordinates": [0.0, 0.0]}
        self.verified = verified
        self.reputation = reputation
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary for MongoDB storage."""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "region": self.region,
            "location": self.location,
            "verified": self.verified,
            "reputation": self.reputation,
            "created_at": self.created_at
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'User':
        """Create User object from dictionary."""
        return User(
            user_id=data.get('user_id'),
            name=data.get('name', ''),
            email=data.get('email', ''),
            region=data.get('region', ''),
            location=data.get('location'),
            verified=data.get('verified', False),
            reputation=data.get('reputation', 0),
            created_at=data.get('created_at')
        )

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate user data.
        Returns (is_valid, error_message).
        """
        if not self.name or len(self.name.strip()) == 0:
            return False, "Name is required"

        if not self.email or '@' not in self.email:
            return False, "Valid email is required"

        if not self.region:
            return False, "Region is required"

        # Validate location structure
        if not isinstance(self.location, dict):
            return False, "Location must be an object"

        if self.location.get('type') != 'Point':
            return False, "Location type must be 'Point'"

        coords = self.location.get('coordinates', [])
        if not isinstance(coords, list) or len(coords) != 2:
            return False, "Location coordinates must be [longitude, latitude]"

        try:
            lon, lat = float(coords[0]), float(coords[1])
            if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                return False, "Invalid coordinate values"
        except (ValueError, TypeError):
            return False, "Coordinates must be numeric values"

        return True, None
