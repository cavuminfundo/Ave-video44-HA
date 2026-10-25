import asyncio
import logging
from typing import Any
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
        """Return supported features. Stream if RTSP URL is available or Cloud SIP session active."""
        if (
            self.coordinator.get_rtsp_url(self.device_id) is not None
            or str(self.device_id) in getattr(self.coordinator, "cloud_sip_sessions", {})
        ):
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
        if hasattr(self.coordinator, "async_wait_for_wake"):
            await self.coordinator.async_wait_for_wake(self.device_id, timeout=10.0)

        if hasattr(self.coordinator, "async_get_camera_frame"):
            sip_frame = await self.coordinator.async_get_camera_frame(self.device_id, timeout=6.0)
            if sip_frame:
                return sip_frame

        url = await self.stream_source()
        if not url:
            return None
        try:
            from homeassistant.components import ffmpeg
            return await ffmpeg.async_get_image(
                self.hass, url, extra_cmd="-rtsp_transport tcp", width=width, height=height
            )
        except Exception as err:
            _LOGGER.debug("Error generating camera image via ffmpeg: %s", err)
            return None

    async def handle_async_mjpeg_stream(
        self, request: Any
    ) -> Any:
        """Serve live MJPEG stream from Cloud SIP session or RTSP via FFmpeg."""
        if hasattr(self.coordinator, "async_wait_for_wake"):
            await self.coordinator.async_wait_for_wake(self.device_id, timeout=10.0)

        sessions = getattr(self.coordinator, "cloud_sip_sessions", {})
        if str(self.device_id) in sessions:
            session = sessions[str(self.device_id)]
            frame = await session.wait_for_first_frame(timeout=8.0)
            if frame is not None:
                try:
                    from aiohttp import web
                    response = web.StreamResponse(
                        status=200,
                        reason="OK",
                        headers={
                            "Content-Type": "multipart/x-mixed-replace; boundary=--frameboundary",
                            "Cache-Control": "no-cache, no-store, must-revalidate",
                        },
                    )
                    await response.prepare(request)
                    header = (
                        f"--frameboundary\r\n"
                        f"Content-Type: image/jpeg\r\n"
                        f"Content-Length: {len(frame)}\r\n\r\n"
                    ).encode("utf-8")
                    part = header + frame + b"\r\n"
                    await response.write(part)

                    last_seq = session.frame_seq
                    while session.is_active:
                        last_seq, new_frame = await session.wait_for_next_frame(last_seq, timeout=0.5)
                        cur_frame = new_frame or session.latest_frame
                        if cur_frame:
                            p_header = (
                                f"--frameboundary\r\n"
                                f"Content-Type: image/jpeg\r\n"
                                f"Content-Length: {len(cur_frame)}\r\n\r\n"
                            ).encode("utf-8")
                            p = p_header + cur_frame + b"\r\n"
                            await response.write(p)
                    return response
                except (ConnectionResetError, asyncio.CancelledError):
                    return response
                except Exception as stream_err:
                    _LOGGER.debug("Cloud SIP MJPEG stream error: %s", stream_err)

        url = await self.stream_source()
        if not url:
            return None
        try:
            from haffmpeg.camera import CameraMjpeg
            from homeassistant.components.ffmpeg import DATA_FFMPEG
            from aiohttp import web

            ffmpeg_manager = self.hass.data.get(DATA_FFMPEG)
            if not ffmpeg_manager:
                return None

            stream = CameraMjpeg(ffmpeg_manager.binary)
            await stream.open_camera(url, extra_cmd="-rtsp_transport tcp")
            try:
                stream_reader = await stream.get_reader()
                response = web.StreamResponse(
                    status=200,
                    reason="OK",
                    headers={"Content-Type": "multipart/x-mixed-replace;boundary=--frame"},
                )
                await response.prepare(request)
                while True:
                    data = await stream_reader.read_output()
                    if not data:
                        break
                    await response.write(data)
                return response
            finally:
                await stream.close()
        except Exception as err:
            _LOGGER.debug("Error handling async mjpeg stream: %s", err)
            return None

