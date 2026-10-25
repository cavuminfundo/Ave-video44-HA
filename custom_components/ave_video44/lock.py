"""Lock platform for AVE Video V44 pedestrian and driveway locks."""

import asyncio
import logging
from typing import Any, Optional

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_UNLOCK_PULSE_DURATION, DEFAULT_UNLOCK_PULSE_DURATION, DOMAIN
from .coordinator import AveVideo44Coordinator
from .entity import AveVideo44BaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AVE Video V44 lock entities."""
    coordinator: AveVideo44Coordinator = entry.runtime_data or hass.data[DOMAIN]["entries"][entry.entry_id]

    entities: list[AveVideo44Lock] = []
    for device in coordinator.devices:
        dev_id = device.get("deviceId")
        if dev_id:
            entities.append(
                AveVideo44Lock(coordinator, dev_id, lock_id=1, name="Serratura Pedonale")
            )
            entities.append(
                AveVideo44Lock(coordinator, dev_id, lock_id=2, name="Cancello Carraio")
            )

    async_add_entities(entities)


class AveVideo44Lock(AveVideo44BaseEntity, LockEntity):
    """Lock entity representing a gate or pedestrian door on AVE monitor."""

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
        lock_id: int = 1,
        name: str = "Lock",
    ) -> None:
        super().__init__(coordinator, device_id, unique_key=f"lock_{lock_id}")
        self._lock_id = lock_id
        self._attr_name = name
        if str(lock_id) == "1":
            self._attr_translation_key = "pedestrian"
            self._attr_icon = "mdi:door"
        else:
            self._attr_translation_key = "driveway"
            self._attr_icon = "mdi:gate"
        self._attr_is_locked = True
        self._relock_task: Optional[asyncio.Task] = None

    @property
    def is_locked(self) -> bool:
        """Return true if lock is currently locked."""
        return self._attr_is_locked

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock door/gate and schedule automatic relock."""
        _LOGGER.debug("Unlocking lock %s on device %s", self._lock_id, self.device_id)
        await self.coordinator.async_unlock(
            device_id=self.device_id,
            lock_id=str(self._lock_id),
        )

        self._attr_is_locked = False
        self.async_write_ha_state()

        if self._relock_task and not self._relock_task.done():
            self._relock_task.cancel()

        pulse_duration = self.coordinator.entry.options.get(
            CONF_UNLOCK_PULSE_DURATION, DEFAULT_UNLOCK_PULSE_DURATION
        )
        self._relock_task = asyncio.create_task(self._auto_relock(pulse_duration))

    async def _auto_relock(self, delay: int) -> None:
        """Reset lock state after configured pulse duration."""
        try:
            await asyncio.sleep(delay)
            self._attr_is_locked = True
            self.async_write_ha_state()
        except asyncio.CancelledError:
            pass

    async def async_lock(self, **kwargs: Any) -> None:
        """Force manual relock."""
        if self._relock_task and not self._relock_task.done():
            self._relock_task.cancel()
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel background timer on entity removal."""
        if self._relock_task and not self._relock_task.done():
            self._relock_task.cancel()
            self._relock_task = None
        await super().async_will_remove_from_hass()
