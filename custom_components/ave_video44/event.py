"""Event platform for AVE Video V44 doorbell and intercom ringing events."""

from typing import Any, Callable, Dict, Optional
from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AveVideo44Coordinator
from .entity import AveVideo44BaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AVE Video V44 event entities."""
    coordinator: AveVideo44Coordinator = entry.runtime_data or hass.data[DOMAIN]["entries"][entry.entry_id]

    entities: list[AveVideo44DoorbellEvent] = []
    for device in coordinator.devices:
        dev_id = device.get("deviceId")
        if dev_id:
            entities.append(AveVideo44DoorbellEvent(coordinator, dev_id))

    async_add_entities(entities)


class AveVideo44DoorbellEvent(AveVideo44BaseEntity, EventEntity):
    """Event entity firing doorbell and intercom ring notifications."""

    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = ["doorstation_ring", "intercom_ring"]

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
    ) -> None:
        super().__init__(coordinator, device_id, unique_key="doorbell_event")
        self._attr_name = "Campanello"
        self._attr_translation_key = "doorbell"
        self._attr_icon = "mdi:doorbell-video"
        self._unsub_ring: Optional[Callable[[], None]] = None

    @property
    def event_types(self) -> list[str]:
        """Return list of supported event types."""
        return self._attr_event_types

    async def async_added_to_hass(self) -> None:
        """Register ring event listener when entity added."""
        await super().async_added_to_hass()
        self._unsub_ring = self.coordinator.register_ring_callback(self._handle_ring_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister listener on removal."""
        if self._unsub_ring:
            self._unsub_ring()
            self._unsub_ring = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_ring_callback(self, ring_type: str, event_data: Dict[str, Any]) -> None:
        """Fire event when ring matches this monitor."""
        if str(event_data.get("device_id")) == self.device_id or event_data.get("device_id") == "default":
            self._trigger_event(ring_type, event_data)
            self.async_write_ha_state()

    @callback
    def handle_coordinator_update(self) -> None:
        """Handle coordinator state updates."""
        if self.coordinator.last_ring_event:
            ev = self.coordinator.last_ring_event
            if str(ev.get("device_id")) == self.device_id or ev.get("device_id") == "default":
                self._trigger_event(ev.get("ring_type", "doorstation_ring"), ev)
                self.async_write_ha_state()
