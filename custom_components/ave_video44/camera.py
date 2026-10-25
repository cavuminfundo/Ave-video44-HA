"""Camera platform for AVE Video V44 RTSP stream."""

import logging
from homeassistant.components.camera import Camera, CameraEntityFeature
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
    """Set up AVE Video V44 camera entities."""
    coordinator: AveVideo44Coordinator = entry.runtime_data or hass.data[DOMAIN]["entries"][entry.entry_id]

    entities: list[AveVideo44Camera] = []
    for device in coordinator.devices:
        dev_id = device.get("deviceId")
        if dev_id:
            entities.append(AveVideo44Camera(coordinator, dev_id))

    async_add_entities(entities)


class AveVideo44Camera(AveVideo44BaseEntity, Camera):
    """Camera entity providing RTSP stream from doorstation or indoor monitor."""

    def __init__(
        self,
        coordinator: AveVideo44Coordinator,
        device_id: int | str,
    ) -> None:
        AveVideo44BaseEntity.__init__(self, coordinator, device_id, unique_key="camera")
        Camera.__init__(self)
        self._attr_name = "Telecamera"
        self._attr_translation_key = "live_stream"
        self._attr_icon = "mdi:cctv"

    @property
    def supported_features(self) -> CameraEntityFeature:
        """Return supported features. Stream only if an RTSP URL is available."""
        if self.coordinator.get_rtsp_url(self.device_id) is not None:
            return CameraEntityFeature.STREAM
        try:
            return CameraEntityFeature(0)
        except TypeError:
            return 0  # type: ignore[return-value]

    @supported_features.setter
    def supported_features(self, value: CameraEntityFeature) -> None:
        """Allow base class or tests to assign supported_features."""
        self._attr_supported_features = value

    async def stream_source(self) -> str | None:
        """Return RTSP URL for live preview stream."""
        return self.coordinator.get_rtsp_url(self.device_id)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        return None
