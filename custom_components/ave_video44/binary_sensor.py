"""Binary sensor platform for AVE Video V44 incoming call and connectivity."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up AVE Video V44 binary sensors."""
    coordinator: AveVideo44Coordinator = entry.runtime_data or hass.data[DOMAIN]["entries"][entry.entry_id]

    entities: list[BinarySensorEntity] = []
    for device in coordinator.devices:
        dev_id = device.get("deviceId")
        if dev_id:
            entities.append(
                AveVideo44IncomingCallBinarySensor(coordinator, dev_id)
            )
            entities.append(
                AveVideo44OnlineBinarySensor(coordinator, dev_id)
            )

    async_add_entities(entities)


class AveVideo44IncomingCallBinarySensor(AveVideo44BaseEntity, BinarySensorEntity):
    """Sensor reporting whether an incoming doorbell/intercom call is ringing."""

    _attr_device_class = BinarySensorDeviceClass.SOUND

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
    ) -> None:
        super().__init__(coordinator, device_id, unique_key="incoming_call")
        self._attr_name = "Chiamata in Arrivo"
        self._attr_translation_key = "incoming_call"
        self._attr_icon = "mdi:phone-ring"

    @property
    def is_on(self) -> bool:
        """Return true when monitor is ringing."""
        return self.coordinator.call_state == "ringing"


class AveVideo44OnlineBinarySensor(AveVideo44BaseEntity, BinarySensorEntity):
    """Sensor reporting whether the monitor is connected and online."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
    ) -> None:
        super().__init__(coordinator, device_id, unique_key="connectivity")
        self._attr_name = "Connessione"
        self._attr_translation_key = "connectivity"
        self._attr_icon = "mdi:lan-check"

    @property
    def is_on(self) -> bool:
        """Return true if device reports online status."""
        dev = self._get_device_data()
        return bool(dev.get("isOnline", 1))
