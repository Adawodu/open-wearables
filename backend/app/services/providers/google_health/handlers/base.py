"""Base interface for Google Health Connect data source handlers."""

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.event_record import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate


class GoogleHealthSourceHandler(ABC):
    """Base interface for Google Health Connect data source handlers."""

    @abstractmethod
    def normalize(self, data: Any) -> list[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """Normalizes raw data from a specific Google Health source into unified event records.

        Args:
            data: Raw data from the Google Health Connect source

        Returns:
            List of tuples containing (EventRecordCreate, EventRecordDetailCreate)
        """
        pass
