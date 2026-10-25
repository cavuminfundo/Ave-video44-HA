"""Button platform for AVE Video V44 actions."""

import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AveVideo44Coordinator
from .entity import AveVideo44BaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AVE Video V44 button entities."""
    coordinator: AveVideo44Coordinator = entry.runtime_data or hass.data[DOMAIN]["entries"][entry.entry_id]

    entities: list[ButtonEntity] = []
    for device in coordinator.devices:
        dev_id = device.get("deviceId")
        if dev_id:
            entities.extend([
                AveVideo44UnlockButton(coordinator, dev_id, lock_id=1, name="Apriporta Pedonale"),
                AveVideo44UnlockButton(coordinator, dev_id, lock_id=2, name="Apriporta Carraio"),
                AveVideo44CallButton(coordinator, dev_id, name="Chiama Interfono"),
                AveVideo44AnswerButton(coordinator, dev_id, name="Rispondi"),
                AveVideo44HangupButton(coordinator, dev_id, name="Riaggancia"),
                AveVideo44WakeCameraButton(coordinator, dev_id, name="Attiva Telecamera"),
            ])

    async_add_entities(entities)


class AveVideo44UnlockButton(AveVideo44BaseEntity, ButtonEntity):
    """Button to unlock pedestrian or gate."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
        lock_id: int = 1,
        name: str = "Apriporta",
    ) -> None:
        super().__init__(coordinator, device_id, unique_key=f"btn_unlock_{lock_id}")
        self._lock_id = lock_id
        self._attr_name = name
        if str(lock_id) == "1":
            self._attr_translation_key = "unlock_1"
            self._attr_icon = "mdi:door-open"
        else:
            self._attr_translation_key = "unlock_2"
            self._attr_icon = "mdi:gate-open"

    async def async_press(self) -> None:
        """Trigger unlock."""
        if self.coordinator.api:
            await self.coordinator.api.unlock(
                device_id=self.device_id,
                lock_id=str(self._lock_id),
            )


class AveVideo44CallButton(AveVideo44BaseEntity, ButtonEntity):
    """Button to initiate intercom call to selected target."""

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
        name: str = "Chiama Interfono",
    ) -> None:
        super().__init__(coordinator, device_id, unique_key="btn_call")
        self._attr_name = name
        self._attr_translation_key = "call"
        self._attr_icon = "mdi:phone-outgoing"

    async def async_press(self) -> None:
        """Initiate call."""
        await self.coordinator.async_call_intercom(self.device_id)


class AveVideo44AnswerButton(AveVideo44BaseEntity, ButtonEntity):
    """Button to answer incoming call."""

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
        name: str = "Rispondi",
    ) -> None:
        super().__init__(coordinator, device_id, unique_key="btn_answer")
        self._attr_name = name
        self._attr_translation_key = "answer"
        self._attr_icon = "mdi:phone"

    async def async_press(self) -> None:
        """Answer incoming call."""
        await self.coordinator.async_answer_call(self.device_id)


class AveVideo44HangupButton(AveVideo44BaseEntity, ButtonEntity):
    """Button to hangup active or ringing call."""

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
        name: str = "Riaggancia",
    ) -> None:
        super().__init__(coordinator, device_id, unique_key="btn_hangup")
        self._attr_name = name
        self._attr_translation_key = "hangup"
        self._attr_icon = "mdi:phone-hangup"

    async def async_press(self) -> None:
        """Hang up call."""
        await self.coordinator.async_hangup_call(self.device_id)


class AveVideo44WakeCameraButton(AveVideo44BaseEntity, ButtonEntity):
    """Button to wake outdoor camera / start live monitoring."""

    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
        name: str = "Attiva Telecamera",
    ) -> None:
        super().__init__(coordinator, device_id, unique_key="btn_wake_camera")
        self._attr_name = name
        self._attr_translation_key = "wake_camera"
        self._attr_icon = "mdi:cctv"

    async def async_press(self) -> None:
        """Wake camera / start monitoring."""
        await self.coordinator.async_wake_camera(self.device_id)

