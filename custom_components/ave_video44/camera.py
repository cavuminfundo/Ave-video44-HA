import asyncio
import logging
import time
from typing import Any, Optional
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AveVideo44Coordinator
from .entity import AveVideo44BaseEntity

_LOGGER = logging.getLogger(__name__)

MAX_MJPEG_RENEWALS: int = 20
MAX_CONSECUTIVE_RENEW_FAILURES: int = 3
PRE_RENEW_AFTER_S: float = 16.0


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
        if hasattr(self.coordinator, "notify_frame_read"):
            self.coordinator.notify_frame_read(self.device_id)

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

    async def _run_pre_renewal(self, device_id: str) -> tuple[Any, Optional[bytes]]:
        """Pre-emptively prepare a new SIP session and await its first frame."""
        new_sess = None
        t0 = time.monotonic()
        try:
            if hasattr(self.coordinator, "async_prepare_renewal_session"):
                new_sess = await self.coordinator.async_prepare_renewal_session(device_id)
            if not new_sess:
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                _LOGGER.warning(
                    "pre-renew failed stage=prepare_none elapsed_ms=%d reason=coordinator_none",
                    elapsed_ms,
                )
                return None, None
            new_frame = await new_sess.wait_for_first_frame(timeout=8.0)
            if new_frame is None:
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                _LOGGER.warning(
                    "pre-renew failed stage=first_frame_timeout elapsed_ms=%d reason=first_frame_timeout",
                    elapsed_ms,
                )
                await new_sess.async_stop()
                return None, None
            return new_sess, new_frame
        except asyncio.CancelledError:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            _LOGGER.warning(
                "pre-renew failed stage=cancelled elapsed_ms=%d reason=cancelled",
                elapsed_ms,
            )
            if new_sess:
                try:
                    await new_sess.async_stop()
                except Exception:
                    pass
            raise
        except Exception as err:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            _LOGGER.warning(
                "pre-renew failed stage=exception elapsed_ms=%d reason=%s",
                elapsed_ms,
                type(err).__name__,
            )
            if new_sess:
                try:
                    await new_sess.async_stop()
                except Exception:
                    pass
            return None, None

    async def handle_async_mjpeg_stream(
        self, request: Any
    ) -> Any:
        """Serve live MJPEG stream from Cloud SIP session or RTSP via FFmpeg."""
        if hasattr(self.coordinator, "notify_frame_read"):
            self.coordinator.notify_frame_read(self.device_id)

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
                    drain_fn = getattr(response, "drain", None)
                    if callable(drain_fn):
                        drain_res = drain_fn()
                        if asyncio.iscoroutine(drain_res):
                            await drain_res
                    served_frames = 1
                    last_send_ts = time.monotonic()
                    last_serve_log = last_send_ts
                    max_send_gap_ms = 0.0

                    renewals = 0
                    consecutive_failures = 0
                    pre_renew_task: Optional[asyncio.Task] = None
                    last_seq = session.frame_seq
                    session_start_ts = last_send_ts
                    pre_renew_attempted = False

                    async def _swap_to(new_sess: Any, first_frame: bytes) -> None:
                        nonlocal session, session_start_ts, pre_renew_attempted
                        nonlocal renewals, consecutive_failures, last_seq
                        nonlocal served_frames, last_send_ts, pre_renew_task
                        now = time.monotonic()
                        gap_ms = int((now - last_send_ts) * 1000.0) if last_send_ts > 0.0 else 0
                        _LOGGER.info("pre-renew swap ok gap_ms=%d", gap_ms)
                        if hasattr(self.coordinator, "async_commit_session"):
                            await self.coordinator.async_commit_session(self.device_id, new_sess)
                        else:
                            try:
                                await session.async_stop()
                            except Exception:
                                pass
                        session = new_sess
                        pre_renew_task = None
                        session_start_ts = time.monotonic()
                        pre_renew_attempted = False
                        renewals += 1
                        consecutive_failures = 0
                        last_seq = session.frame_seq

                        p_header = (
                            f"--frameboundary\r\n"
                            f"Content-Type: image/jpeg\r\n"
                            f"Content-Length: {len(first_frame)}\r\n\r\n"
                        ).encode("utf-8")
                        p = p_header + first_frame + b"\r\n"
                        await response.write(p)
                        drain_fn = getattr(response, "drain", None)
                        if callable(drain_fn):
                            drain_res = drain_fn()
                            if asyncio.iscoroutine(drain_res):
                                await drain_res
                        served_frames += 1
                        last_send_ts = time.monotonic()

                    try:
                        while True:
                            last_seq = session.frame_seq
                            session_start_ts = time.monotonic()
                            pre_renew_attempted = False

                            while session.is_active:
                                if hasattr(self.coordinator, "notify_frame_read"):
                                    self.coordinator.notify_frame_read(self.device_id)
                                next_seq, new_frame = await session.wait_for_next_frame(last_seq, timeout=0.5)
                                if next_seq > last_seq and new_frame is not None:
                                    last_seq = next_seq
                                    p_header = (
                                        f"--frameboundary\r\n"
                                        f"Content-Type: image/jpeg\r\n"
                                        f"Content-Length: {len(new_frame)}\r\n\r\n"
                                    ).encode("utf-8")
                                    p = p_header + new_frame + b"\r\n"
                                    await response.write(p)
                                    drain_fn = getattr(response, "drain", None)
                                    if callable(drain_fn):
                                        drain_res = drain_fn()
                                        if asyncio.iscoroutine(drain_res):
                                            await drain_res
                                    served_frames += 1
                                    now = time.monotonic()
                                    if last_send_ts > 0.0:
                                        gap_ms = (now - last_send_ts) * 1000.0
                                        if gap_ms > max_send_gap_ms:
                                            max_send_gap_ms = gap_ms
                                    last_send_ts = now

                                now = time.monotonic()
                                if now - last_serve_log >= 5.0:
                                    _LOGGER.debug(
                                        "mjpeg serve frames=%d max_send_gap_ms=%.0f",
                                        served_frames,
                                        max_send_gap_ms,
                                    )
                                    last_serve_log = now
                                    max_send_gap_ms = 0.0

                                # Trigger pre-emptive renewal before cloud BYE (~32s)
                                user_hungup = False
                                if hasattr(self.coordinator, "user_hangup"):
                                    user_hungup = str(self.device_id) in self.coordinator.user_hangup

                                session_age = now - session_start_ts
                                if (
                                    session.is_active
                                    and session_age >= PRE_RENEW_AFTER_S
                                    and not user_hungup
                                    and renewals < MAX_MJPEG_RENEWALS
                                    and pre_renew_task is None
                                    and not pre_renew_attempted
                                ):
                                    pre_renew_attempted = True
                                    _LOGGER.info("pre-renew started age=%.1fs", session_age)
                                    pre_renew_task = asyncio.create_task(
                                        self._run_pre_renewal(str(self.device_id))
                                    )

                                if pre_renew_task and pre_renew_task.done():
                                    try:
                                        new_sess, first_frame = pre_renew_task.result()
                                    except Exception as task_err:
                                        _LOGGER.debug("pre-renew task exception: %s", task_err)
                                        new_sess, first_frame = None, None

                                    if new_sess and first_frame:
                                        await _swap_to(new_sess, first_frame)
                                        continue
                                    else:
                                        pre_renew_task = None
                                        _LOGGER.warning("pre-renew failed, fallback")

                            if pre_renew_task is not None:
                                try:
                                    new_sess, first_frame = await asyncio.wait_for(pre_renew_task, timeout=5.0)
                                except Exception:
                                    new_sess, first_frame = None, None
                                if new_sess and first_frame:
                                    await _swap_to(new_sess, first_frame)
                                    continue
                                else:
                                    pre_renew_task = None
                                    _LOGGER.warning("pre-renew failed, fallback")

                            user_hungup = False
                            if hasattr(self.coordinator, "user_hangup"):
                                user_hungup = str(self.device_id) in self.coordinator.user_hangup

                            is_remote_bye = getattr(session, "remote_bye", False) is True
                            if not is_remote_bye or user_hungup or renewals >= MAX_MJPEG_RENEWALS:
                                break

                            renew_success = False
                            while consecutive_failures < MAX_CONSECUTIVE_RENEW_FAILURES and not renew_success:
                                if hasattr(self.coordinator, "async_wake_camera"):
                                    try:
                                        await self.coordinator.async_wake_camera(self.device_id)
                                    except Exception as wake_err:
                                        _LOGGER.debug("Error waking camera for renewal: %s", wake_err)

                                if hasattr(self.coordinator, "async_wait_for_wake"):
                                    await self.coordinator.async_wait_for_wake(self.device_id, timeout=8.0)

                                current_sessions = getattr(self.coordinator, "cloud_sip_sessions", {})
                                new_session = current_sessions.get(str(self.device_id))
                                if not new_session or new_session is session:
                                    consecutive_failures += 1
                                    if consecutive_failures >= MAX_CONSECUTIVE_RENEW_FAILURES:
                                        break
                                    await asyncio.sleep(0.5)
                                    continue

                                new_frame = await new_session.wait_for_first_frame(timeout=8.0)
                                if new_frame is None:
                                    consecutive_failures += 1
                                    if consecutive_failures >= MAX_CONSECUTIVE_RENEW_FAILURES:
                                        break
                                    await asyncio.sleep(0.5)
                                    continue

                                renew_success = True
                                consecutive_failures = 0
                                renewals += 1
                                session = new_session
                                session_start_ts = time.monotonic()
                                _LOGGER.debug("mjpeg session renewed after remote BYE n=%d", renewals)

                                p_header = (
                                    f"--frameboundary\r\n"
                                    f"Content-Type: image/jpeg\r\n"
                                    f"Content-Length: {len(new_frame)}\r\n\r\n"
                                ).encode("utf-8")
                                p = p_header + new_frame + b"\r\n"
                                await response.write(p)
                                drain_fn = getattr(response, "drain", None)
                                if callable(drain_fn):
                                    drain_res = drain_fn()
                                    if asyncio.iscoroutine(drain_res):
                                        await drain_res
                                served_frames += 1
                                now = time.monotonic()
                                if last_send_ts > 0.0:
                                    gap_ms = (now - last_send_ts) * 1000.0
                                    if gap_ms > max_send_gap_ms:
                                        max_send_gap_ms = gap_ms
                                last_send_ts = now

                            if not renew_success:
                                break

                        return response
                    finally:
                        if pre_renew_task:
                            if not pre_renew_task.done():
                                pre_renew_task.cancel()
                                try:
                                    await pre_renew_task
                                except (asyncio.CancelledError, Exception):
                                    pass
                            else:
                                try:
                                    res_tuple = pre_renew_task.result()
                                    new_s = res_tuple[0] if isinstance(res_tuple, tuple) and res_tuple else None
                                    if new_s and new_s is not session:
                                        try:
                                            await new_s.async_stop()
                                        except Exception:
                                            pass
                                except (asyncio.CancelledError, Exception):
                                    pass

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

