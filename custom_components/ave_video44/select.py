"""Select platform for AVE Video V44 intercom target selection."""

import logging
from homeassistant.components.select import SelectEntity
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
    """Set up AVE Video V44 intercom select entities."""
    coordinator: AveVideo44Coordinator = entry.runtime_data or hass.data[DOMAIN]["entries"][entry.entry_id]

    entities: list[AveVideo44IntercomTargetSelect] = []
    for device in coordinator.devices:
        dev_id = device.get("deviceId")
        if dev_id:
            entities.append(AveVideo44IntercomTargetSelect(coordinator, dev_id))

    async_add_entities(entities)


class AveVideo44IntercomTargetSelect(AveVideo44BaseEntity, SelectEntity):
    """Dropdown entity to select intercom destination room from book."""

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
    ) -> None:
        super().__init__(coordinator, device_id, unique_key="intercom_target")
        self._attr_name = "Destinazione Interfono"
        self._attr_current_option = None
        self._init_options()

    def _init_options(self) -> None:
        """Build options list from coordinator intercom book."""
        opts = []
        for code, name in self.coordinator.intercom_book.items():
            opts.append(f"{code} ({name})")
        self._attr_options = opts
        if opts and (self._attr_current_option not in opts):
            self._attr_current_option = opts[0]
            self.coordinator.selected_intercom_targets[self.device_id] = self.selected_room_code

    @property
    def current_option(self) -> str | None:
        """Return currently selected target."""
        return self._attr_current_option

    @property
    def options(self) -> list[str]:
        """Return available intercom targets."""
        opts = [f"{code} ({name})" for code, name in self.coordinator.intercom_book.items()]
        return opts or self._attr_options

    @property
    def selected_room_code(self) -> str:
        """Extract room code part from current option."""
        if not self._attr_current_option:
            return ""
        return self._attr_current_option.split(" (", 1)[0].strip()

    async def async_select_option(self, option: str) -> None:
        """Set new selected destination."""
        self._attr_current_option = option
        self.coordinator.selected_intercom_targets[self.device_id] = self.selected_room_code
        self.async_write_ha_state()
