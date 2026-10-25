"""Base entity for AVE Video V44 integration."""

from typing import Any, Dict
try:
    from homeassistant.helpers.device_registry import DeviceInfo
except ImportError:
    from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AveVideo44Coordinator


class AveVideo44BaseEntity(CoordinatorEntity[AveVideo44Coordinator]):
    """Common base for all AVE Video V44 entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
        unique_key: str,
    ) -> None:
        super().__init__(coordinator)
        self.device_id = str(device_id)
        self._attr_unique_id = f"{coordinator.entry_id}_{self.device_id}_{unique_key}"

        dev = self._get_device_data()
        model = dev.get("deviceModel") or dev.get("className") or "V44 Intercom"
        name = dev.get("deviceName") or dev.get("name") or f"Monitor {self.device_id}"
        sw_version = dev.get("firmwareVersion") or dev.get("version") or "1.0"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=name,
            manufacturer="AVE",
            model=model,
            sw_version=sw_version,
            configuration_url=f"http://{dev.get('ip')}" if dev.get("ip") else None,
        )

    def _get_device_data(self) -> Dict[str, Any]:
        """Return dict of device properties from coordinator."""
        for d in self.coordinator.devices:
            if str(d.get("deviceId")) == self.device_id:
                return d
        return {"deviceId": self.device_id}

    @property
    def available(self) -> bool:
        """Return true if device is online and coordinator is available."""
        if not super().available:
            return False
        dev = self._get_device_data()
        return bool(dev.get("isOnline", 1))
