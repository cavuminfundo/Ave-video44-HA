"""AVE Video V44 Cloud REST API client."""

import time
from typing import Any, Dict, List, Optional
import aiohttp

from ..const import (
    DEFAULT_APP_SECRET,
    DEFAULT_APP_UUID,
    DEFAULT_BASE_URL,
    DEFAULT_TENANT_UUID,
)
from .protocol import compute_gvs_sign, hash_password_sha256


class AveCloudApi:
    """Async client for AVE / GVS Cloud REST API."""

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        base_url: str = DEFAULT_BASE_URL,
        tenant_uuid: str = DEFAULT_TENANT_UUID,
        app_uuid: str = DEFAULT_APP_UUID,
        app_secret: str = DEFAULT_APP_SECRET,
        token: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self._session = session
        self._own_session = False
        self._base_url = base_url.rstrip("/")
        self._tenant_uuid = tenant_uuid
        self._app_uuid = app_uuid
        self._app_secret = app_secret
        self.token = token
        self.session_id = session_id

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    def _prepare_payload(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Attach tenant, app, timestamp and computed signature."""
        data = {
            "tenantUuid": self._tenant_uuid,
            "appUuid": self._app_uuid,
            "ts": int(time.time() * 1000),
            **params,
        }
        data["sign"] = compute_gvs_sign(data, secret=self._app_secret)
        return data

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            headers["token"] = self.token
            headers["Authorization"] = f"Bearer {self.token}"
        if self.session_id:
            headers["sessionId"] = self.session_id
        return headers

    async def login_with_password(self, account: str, password: str) -> Dict[str, Any]:
        """Authenticate with account username/email and password."""
        session = await self._get_session()
        payload = self._prepare_payload({
            "account": account,
            "password": hash_password_sha256(password),
            "channel": "App",
        })
        url = f"{self._base_url}/usercenter/api/uc/loginToGvs/account"
        async with session.post(url, json=payload, headers=self._get_headers()) as resp:
            resp_data = await resp.json()
            data = resp_data.get("data", {})
            self.token = data.get("token")
            self.session_id = data.get("sessionId")
            return data

    async def request_otp(self, email: str) -> Dict[str, Any]:
        """Request email OTP verification code."""
        session = await self._get_session()
        payload = self._prepare_payload({"email": email})
        url = f"{self._base_url}/usercenter/api/uc/otp/request/email"
        async with session.post(url, json=payload, headers=self._get_headers()) as resp:
            return await resp.json()

    async def login_with_otp(self, email: str, code: str) -> Dict[str, Any]:
        """Authenticate with email and 6-digit OTP code."""
        session = await self._get_session()
        payload = self._prepare_payload({
            "email": email,
            "code": code,
            "channel": "App",
        })
        url = f"{self._base_url}/usercenter/api/uc/loginToGvs/email/otp"
        async with session.post(url, json=payload, headers=self._get_headers()) as resp:
            resp_data = await resp.json()
            data = resp_data.get("data", {})
            self.token = data.get("token")
            self.session_id = data.get("sessionId")
            return data

    async def get_home_list(self) -> List[Dict[str, Any]]:
        """Fetch registered homes / installations for the authenticated user."""
        session = await self._get_session()
        params = self._prepare_payload({})
        url = f"{self._base_url}/smarthome/api/user/home/getHomeList"
        async with session.get(url, params=params, headers=self._get_headers()) as resp:
            resp_data = await resp.json()
            return resp_data.get("data", [])

    async def get_devices(self, home_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch devices (doorstations, indoor monitors, cameras) for a home."""
        session = await self._get_session()
        raw_params: Dict[str, Any] = {}
        if home_id:
            raw_params["homeId"] = home_id
        params = self._prepare_payload(raw_params)
        url = f"{self._base_url}/smarthome/api/user/device/getDeviceList"
        async with session.get(url, params=params, headers=self._get_headers()) as resp:
            resp_data = await resp.json()
            return resp_data.get("data", [])

    async def unlock(
        self,
        device_id: str,
        lock_id: str = "1",
        monitoring_device_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send remote unlock command (lockId: 1 for pedestrian, 2 for gate)."""
        session = await self._get_session()
        payload_data: Dict[str, Any] = {
            "deviceId": device_id,
            "lockId": str(lock_id),
        }
        if monitoring_device_number:
            payload_data["monitoringDeviceNumber"] = monitoring_device_number

        payload = self._prepare_payload(payload_data)
        url = f"{self._base_url}/smarthome/api/device-monitoring/unlock"
        async with session.post(url, json=payload, headers=self._get_headers()) as resp:
            return await resp.json()

    async def get_sip_account(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch dynamic SIP extension credentials for the device."""
        session = await self._get_session()
        raw_params: Dict[str, Any] = {}
        if device_id:
            raw_params["deviceId"] = device_id
        params = self._prepare_payload(raw_params)
        url = f"{self._base_url}/smarthome/api/user/sip/getSipAccount"
        async with session.get(url, params=params, headers=self._get_headers()) as resp:
            resp_data = await resp.json()
            return resp_data.get("data", {})

    async def get_rtsp_config(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch RTSP video stream configuration for live preview."""
        session = await self._get_session()
        raw_params: Dict[str, Any] = {}
        if device_id:
            raw_params["deviceId"] = device_id
        params = self._prepare_payload(raw_params)
        url = f"{self._base_url}/smarthome/api/user/rtsp/auth/config"
        async with session.get(url, params=params, headers=self._get_headers()) as resp:
            resp_data = await resp.json()
            return resp_data.get("data", {})

    async def async_close(self) -> None:
        """Close client session if owned."""
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> "AveCloudApi":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.async_close()
