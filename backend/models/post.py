from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid

class Post:
    def __init__(
        self,
        post_id: Optional[str] = None,
        user_id: str = "",
        post_type: str = "help",
        message: str = "",
        location: Optional[Dict[str, Any]] = None,
        region: str = "",
        capacity: Optional[int] = None,
        timestamp: Optional[datetime] = None,
        last_modified: Optional[datetime] = None
    ):
        self.post_id = post_id or str(uuid.uuid4())
        self.user_id = user_id
        self.post_type = post_type
        self.message = message
        self.location = location or {"type": "Point", "coordinates": [0.0, 0.0]}
        self.region = region
        self.capacity = capacity
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.last_modified = last_modified or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "post_id": self.post_id,
            "user_id": self.user_id,
            "post_type": self.post_type,
            "message": self.message,
            "location": self.location,
            "region": self.region,
            "timestamp": self.timestamp,
            "last_modified": self.last_modified
        }

        if self.capacity is not None:
            data["capacity"] = self.capacity

        return data

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Post':
        return Post(
            post_id=data.get('post_id'),
            user_id=data.get('user_id', ''),
            post_type=data.get('post_type', 'help'),
            message=data.get('message', ''),
            location=data.get('location'),
            region=data.get('region', ''),
            capacity=data.get('capacity'),
            timestamp=data.get('timestamp'),
            last_modified=data.get('last_modified')
        )

    def validate(self) -> tuple[bool, Optional[str]]:
        if not self.user_id:
            return False, "User ID is required"

        if not self.post_type:
            return False, "Post type is required"

        valid_types = ['shelter', 'food', 'medical', 'water', 'safety', 'help']
        if self.post_type not in valid_types:
            return False, f"Post type must be one of: {', '.join(valid_types)}"

        if not self.message or len(self.message.strip()) == 0:
            return False, "Message is required"

        if not self.region:
            return False, "Region is required"

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

        if self.post_type == 'shelter' and self.capacity is not None:
            if not isinstance(self.capacity, int) or self.capacity < 0:
                return False, "Capacity must be a non-negative integer"

        return True, None
