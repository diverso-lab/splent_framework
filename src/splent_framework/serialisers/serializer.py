from datetime import datetime
from typing import Any


def convert_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class Serializer:
    def __init__(
        self,
        serialization_fields: dict[str, str],
        related_serializers: dict[str, "Serializer"] | None = None,
    ):
        self.serialization_fields = serialization_fields
        self.related_serializers = related_serializers or {}

    def serialize(self, instance: Any) -> dict[str, Any]:
        serialized_data: dict[str, Any] = {}
        for key, attr_name in self.serialization_fields.items():
            if key in self.related_serializers:
                raw = getattr(instance, attr_name, None)
                # attr_name may be a method (returns the related data) or a plain relation
                related_data = raw() if callable(raw) else raw
                if isinstance(related_data, list):
                    serialized_data[key] = [
                        self.related_serializers[key].serialize(sub)
                        for sub in related_data
                    ]
                else:
                    serialized_data[key] = self.related_serializers[key].serialize(
                        related_data
                    )
            else:
                attr = getattr(instance, attr_name, None)
                if callable(attr):
                    attr = attr()
                serialized_data[key] = convert_value(attr)
        return serialized_data
