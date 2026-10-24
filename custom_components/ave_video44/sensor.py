"""Sensor platform for AVE Video V44 call status, caller name, and history."""

from typing import Any
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AveVideo44Coordinator
from .entity import AveVideo44BaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AVE Video V44 sensors."""
    coordinator: AveVideo44Coordinator = entry.runtime_data or hass.data[DOMAIN]["entries"][entry.entry_id]

    entities: list[SensorEntity] = []
    for device in coordinator.devices:
        dev_id = device.get("deviceId")
        if dev_id:
            entities.extend([
                AveVideo44CallStatusSensor(coordinator, dev_id),
                AveVideo44CallerNameSensor(coordinator, dev_id),
                AveVideo44LastCallSensor(coordinator, dev_id),
            ])

    async_add_entities(entities)


class AveVideo44CallStatusSensor(AveVideo44BaseEntity, SensorEntity):
    """Sensor reporting current call status (idle, ringing, in_call)."""

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
    ) -> None:
        super().__init__(coordinator, device_id, unique_key="call_status")
        self._attr_name = "Stato Chiamata"
        self._attr_translation_key = "call_status"
        self._attr_icon = "mdi:phone-in-talk"

    @property
    def native_value(self) -> str:
        """Return call state."""
        return self.coordinator.call_state


class AveVideo44CallerNameSensor(AveVideo44BaseEntity, SensorEntity):
    """Sensor reporting friendly caller name or room number."""

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
    ) -> None:
        super().__init__(coordinator, device_id, unique_key="caller_name")
        self._attr_name = "Chiamante"
        self._attr_translation_key = "caller_name"
        self._attr_icon = "mdi:card-account-details"

    @property
    def native_value(self) -> str:
        """Return caller name when call active or empty string."""
        return self.coordinator.active_caller_name if self.coordinator.call_state != "idle" else ""


class AveVideo44LastCallSensor(AveVideo44BaseEntity, SensorEntity):
    """Sensor reporting timestamp of last received/placed call."""

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
    ) -> None:
        super().__init__(coordinator, device_id, unique_key="last_call")
        self._attr_name = "Ultima Chiamata"
        self._attr_translation_key = "last_call"
        self._attr_icon = "mdi:history"

    @property
    def native_value(self) -> Any:
        """Return ISO timestamp of last call."""
        return self.coordinator.last_call_time
