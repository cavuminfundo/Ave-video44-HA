"""Asynchronous non-blocking MQTT push event listener for AVE Video V44."""

import json
import logging
from typing import Any, Callable, Dict, List, Optional
import paho.mqtt.client as mqtt

from ..const import (
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_USER,
    DEFAULT_MQTT_PASS,
)

_LOGGER = logging.getLogger(__name__)


class AveMqttListener:
    """Non-blocking TLS MQTT client for AVE / GVS event notifications."""

    def __init__(
        self,
        session_id: str,
        broker_host: str = DEFAULT_MQTT_HOST,
        broker_port: int = DEFAULT_MQTT_PORT,
        device_ids: Optional[List[str]] = None,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        use_tls: bool = True,
        home_id: Optional[Any] = None,
        user_id: Optional[Any] = None,
    ) -> None:
        self._session_id = session_id
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._device_ids = list(device_ids or [])
        self._use_tls = use_tls
        self._home_id = str(home_id) if home_id is not None else None
        self._user_id = str(user_id) if user_id is not None else None
        self._callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        if on_event:
            self._callbacks.append(on_event)

        self._client: Optional[mqtt.Client] = None
        self.is_running = False

    def add_event_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register an event dispatch callback."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_event_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Unregister an event dispatch callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _create_client(self) -> mqtt.Client:
        """Create and configure paho-mqtt client."""
        try:
            from paho.mqtt.enums import CallbackAPIVersion
            client = mqtt.Client(CallbackAPIVersion.VERSION2)
        except (ImportError, AttributeError):
            client = mqtt.Client()

        if self._use_tls:
            client.tls_set()

        if self._home_id:
            client.username_pw_set(username=DEFAULT_MQTT_USER, password=DEFAULT_MQTT_PASS)
        else:
            client.username_pw_set(username=self._session_id, password=self._session_id)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        return client

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, rc: Any, *args: Any) -> None:
        """Subscribe to device and broadcast topics on successful connection."""
        _LOGGER.debug("Connected to AVE MQTT broker, subscribing to topics")
        client.subscribe("smarthome/device/status", qos=1)
        if self._home_id:
            client.subscribe(f"smarthome/device/{self._home_id}", qos=1)
            client.subscribe(f"smarthome/device/status/{self._home_id}", qos=1)
        for dev_id in self._device_ids:
            client.subscribe(f"smarthome/device/{dev_id}", qos=1)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: Any, *args: Any) -> None:
        """Log disconnect event."""
        _LOGGER.debug("Disconnected from AVE MQTT broker with code %s", rc)

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        """Parse incoming MQTT payload and dispatch to callbacks."""
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except Exception as err:
            _LOGGER.warning("Failed to decode MQTT message on %s: %s", message.topic, err)
            return

        code = payload.get("code")
        action = payload.get("action")

        if code == "monitoring":
            event_type = "call_incoming" if action == 1 else "call_ended"
        elif code == "unlock":
            event_type = "unlock"
        else:
            event_type = str(code or "unknown")

        for cb in list(self._callbacks):
            try:
                cb(event_type, payload)
            except Exception as err:
                _LOGGER.error("Error in MQTT event callback: %s", err)

    async def async_start(self) -> None:
        """Start MQTT client asynchronously without blocking."""
        if self.is_running:
            return

        self._client = self._create_client()
        self._client.connect_async(self._broker_host, self._broker_port)
        self._client.loop_start()
        self.is_running = True

    async def async_stop(self) -> None:
        """Stop MQTT client and disconnect cleanly."""
        if not self.is_running or not self._client:
            return

        self._client.loop_stop()
        self._client.disconnect()
        self.is_running = False
