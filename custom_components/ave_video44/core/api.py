"""AVE Video V44 Cloud REST API client."""

import asyncio
import json
import re
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
        self.jsessionid: Optional[str] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    def _signed_query(self, extra_query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build signed query dict conforming to AVE Cloud REST API."""
        q: Dict[str, Any] = {
            "appUuid": self._app_uuid,
            "tenantUuid": self._tenant_uuid,
            "ts": str(int(time.time() * 1000)),
        }
        if extra_query:
            for k, v in extra_query.items():
                if v is not None:
                    q[k] = str(v)
        q["sign"] = compute_gvs_sign(q, self._app_secret)
        return q

    def _prepare_payload(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy helper attaching tenant, app, timestamp and signature."""
        data = {
            "tenantUuid": self._tenant_uuid,
            "appUuid": self._app_uuid,
            "ts": int(time.time() * 1000),
            **params,
        }
        data["sign"] = compute_gvs_sign(data, secret=self._app_secret)
        return data

    def _headers(self, home_id: Optional[Any] = None, form: bool = False) -> Dict[str, str]:
        """Build headers conforming to AVE Cloud REST API."""
        headers: Dict[str, str] = {
            "APP_VERSION": "AVE_2.1.1",
            "Accept-Language": "it",
            "Accept": "application/json",
        }
        if self.session_id:
            headers["sessionId"] = str(self.session_id)
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            headers["token"] = str(self.token)
        if self.jsessionid:
            headers["Cookie"] = f"JSESSIONID={self.jsessionid}"
        if home_id is not None:
            headers["HOME_ID"] = str(home_id)
        if form:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            headers["Content-Type"] = "application/json"
        return headers

    def _get_headers(self) -> Dict[str, str]:
        """Backward-compatible header getter."""
        return self._headers()

    @staticmethod
    def _extract_payload(resp_data: Dict[str, Any], require_success: bool = False) -> Any:
        """Extract envelope payload (result or data) and validate success."""
        if require_success:
            if resp_data.get("success") is False or (
                isinstance(resp_data.get("statusCode"), int) and resp_data["statusCode"] < 0
            ):
                raise ValueError(resp_data.get("message") or "AVE Cloud API error")
        if "result" in resp_data:
            return resp_data["result"]
        return resp_data.get("data")

    def _capture_cookies(self, resp: Any) -> None:
        """Capture JSESSIONID from response cookies or headers."""
        if hasattr(resp, "cookies") and resp.cookies and "JSESSIONID" in resp.cookies:
            cookie_val = resp.cookies["JSESSIONID"]
            self.jsessionid = cookie_val.value if hasattr(cookie_val, "value") else str(cookie_val)
        elif hasattr(resp, "headers") and resp.headers and "Set-Cookie" in resp.headers:
            set_cookie = resp.headers.get("Set-Cookie", "")
            match = re.search(r"JSESSIONID=([^;]+)", set_cookie)
            if match:
                self.jsessionid = match.group(1)

    async def login_with_password(self, account: str, password: str) -> Dict[str, Any]:
        """Authenticate with account username/email and password."""
        session = await self._get_session()
        endpoint = (
            f"{self._base_url}/usercenter/api/uc/loginToGvs/email"
            if "@" in account
            else f"{self._base_url}/usercenter/api/uc/loginToGvs/account"
        )
        params = self._signed_query()
        data = {
            "email": account,
            "account": account,
            "password": hash_password_sha256(password),
            "channel": "App",
        }
        headers = self._headers(form=True)
        async with asyncio.timeout(10.0):
            async with session.post(endpoint, params=params, data=data, headers=headers) as resp:
                self._capture_cookies(resp)
                resp_data = await resp.json()
                payload = self._extract_payload(resp_data, require_success=True)
                res_data = dict(payload) if isinstance(payload, dict) else {}
                self.session_id = res_data.get("sessionId") or res_data.get("token")
                self.token = res_data.get("token") or res_data.get("sessionId")
                if not self.session_id and not self.token and ("statusCode" in resp_data or "success" in resp_data):
                    raise ValueError(resp_data.get("message") or "Invalid authentication response")
                res_data["sessionId"] = self.session_id
                res_data["token"] = self.token
                return res_data

    async def request_otp(self, email: str) -> Dict[str, Any]:
        """Request email OTP verification code."""
        session = await self._get_session()
        url = f"{self._base_url}/usercenter/api/uc/otp/request/email"
        params = self._signed_query()
        data = {"email": email}
        headers = self._headers(form=True)
        async with asyncio.timeout(10.0):
            async with session.post(url, params=params, data=data, headers=headers) as resp:
                self._capture_cookies(resp)
                return await resp.json()

    async def login_with_otp(self, account: str, otp_code: str, otp_token: str = "") -> Dict[str, Any]:
        """Authenticate with email and 6-digit OTP code."""
        session = await self._get_session()
        url = f"{self._base_url}/usercenter/api/uc/loginToGvs/email/otp"
        params = self._signed_query()
        data = {
            "email": account,
            "account": account,
            "code": otp_code,
            "verifyCode": otp_code,
            "token": otp_token,
            "channel": "App",
        }
        headers = self._headers(form=True)
        async with asyncio.timeout(10.0):
            async with session.post(url, params=params, data=data, headers=headers) as resp:
                self._capture_cookies(resp)
                resp_data = await resp.json()
                payload = self._extract_payload(resp_data, require_success=True)
                res_data = dict(payload) if isinstance(payload, dict) else {}
                self.session_id = res_data.get("sessionId") or res_data.get("token")
                self.token = res_data.get("token") or res_data.get("sessionId")
                res_data["sessionId"] = self.session_id
                res_data["token"] = self.token
                return res_data

    async def get_home_list(self) -> List[Dict[str, Any]]:
        """Fetch registered homes / installations for the authenticated user."""
        session = await self._get_session()
        url = f"{self._base_url}/smarthome/api/home/queryHomeList"
        params = self._signed_query()
        headers = self._headers()
        async with asyncio.timeout(10.0):
            async with session.get(url, params=params, headers=headers) as resp:
                self._capture_cookies(resp)
                resp_data = await resp.json()
                payload = self._extract_payload(resp_data)
                if isinstance(payload, list):
                    return payload
                if isinstance(payload, dict):
                    return payload.get("homeList", payload.get("records", []))
                return []

    async def get_homes(self) -> List[Dict[str, Any]]:
        """Alias for get_home_list."""
        return await self.get_home_list()

    async def get_devices(self, home_id: Any = None) -> List[Dict[str, Any]]:
        """Fetch devices (doorstations, indoor monitors, cameras) for a home."""
        session = await self._get_session()
        extra_q = {"homeId": str(home_id)} if home_id is not None else None
        url = f"{self._base_url}/smarthome/api/quick-display-device/user-current-home"
        params = self._signed_query(extra_q)
        headers = self._headers(home_id=home_id)
        devices: List[Dict[str, Any]] = []
        try:
            async with asyncio.timeout(10.0):
                async with session.get(url, params=params, headers=headers) as resp:
                    self._capture_cookies(resp)
                    resp_data = await resp.json()
                    payload = self._extract_payload(resp_data)
                    if isinstance(payload, list):
                        devices = payload
                    elif isinstance(payload, dict):
                        devices = payload.get("deviceList", payload.get("records", []))
        except Exception:
            pass

        if not devices:
            try:
                fallback_url = f"{self._base_url}/smarthome/api/homepage/getHomePageCommonDevices"
                async with asyncio.timeout(10.0):
                    async with session.get(fallback_url, params=params, headers=headers) as resp:
                        self._capture_cookies(resp)
                        resp_data = await resp.json()
                        payload = self._extract_payload(resp_data)
                        if isinstance(payload, list):
                            devices = payload
                        elif isinstance(payload, dict):
                            devices = payload.get("deviceList", payload.get("records", []))
            except Exception:
                pass

        for dev in devices:
            if isinstance(dev, dict) and dev.get("deviceId") and not dev.get("mac"):
                try:
                    info_url = f"{self._base_url}/smarthome/api/device/getInfo"
                    info_params = self._signed_query({"id": str(dev["deviceId"])})
                    async with asyncio.timeout(10.0):
                        async with session.get(info_url, params=info_params, headers=headers) as info_resp:
                            self._capture_cookies(info_resp)
                            info_data = await info_resp.json()
                            info_payload = self._extract_payload(info_data)
                            if isinstance(info_payload, dict):
                                for k in ("mac", "className", "version", "online"):
                                    if k in info_payload and k not in dev:
                                        dev[k] = info_payload[k]
                except Exception:
                    pass

        return devices

    async def unlock_remote(
        self,
        device_id: str,
        lock_id: str = "1",
        monitoring_device_number: str = "1",
        home_id: Optional[Any] = None,
    ) -> bool:
        """Remote unlock returning boolean status."""
        session = await self._get_session()
        params = self._signed_query()
        data = {
            "deviceId": str(device_id),
            "lockId": str(lock_id),
            "monitoringDeviceNumber": str(monitoring_device_number),
        }
        url = f"{self._base_url}/smarthome/api/device-monitoring/unlock"
        headers = self._headers(home_id=home_id, form=True)
        async with asyncio.timeout(10.0):
            async with session.post(url, params=params, data=data, headers=headers) as resp:
                self._capture_cookies(resp)
                resp_data = await resp.json()
                return bool(
                    resp_data.get("success", False)
                    or resp_data.get("code") == 0
                    or str(resp_data.get("statusCode")) in ("200", "0")
                )

    async def unlock(
        self,
        device_id: str,
        lock_id: str = "1",
        monitoring_device_number: Optional[str] = "1",
        home_id: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Send remote unlock command returning response dictionary."""
        session = await self._get_session()
        params = self._signed_query()
        data = {
            "deviceId": str(device_id),
            "lockId": str(lock_id),
            "monitoringDeviceNumber": str(monitoring_device_number or "1"),
        }
        url = f"{self._base_url}/smarthome/api/device-monitoring/unlock"
        headers = self._headers(home_id=home_id, form=True)
        async with asyncio.timeout(10.0):
            async with session.post(url, params=params, data=data, headers=headers) as resp:
                self._capture_cookies(resp)
                return await resp.json()

    async def command_unlock(
        self,
        device_id: str | int,
        lock_id: str | int = "1",
        monitoring_device_number: str = "1",
        home_id: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Send device command control unlock (functionId 23 for lock 1, 24 for lock 2)."""
        session = await self._get_session()
        params = self._signed_query()
        function_id = "24" if str(lock_id) == "2" else "23"
        val = json.dumps(
            {"outDoorNumber": str(monitoring_device_number), "lockStatus": 1},
            separators=(",", ":"),
        )
        data = {
            "id": str(device_id),
            "functionId": function_id,
            "value": val,
            "time": str(int(time.time() * 1000)),
        }
        url = f"{self._base_url}/smarthome/api/device/command/control"
        headers = self._headers(home_id=home_id, form=True)
        async with asyncio.timeout(10.0):
            async with session.post(url, params=params, data=data, headers=headers) as resp:
                self._capture_cookies(resp)
                return await resp.json()


    async def get_sip_account(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch dynamic SIP extension credentials for the device."""
        session = await self._get_session()
        extra_q = {"deviceId": str(device_id)} if device_id else None
        url = f"{self._base_url}/smarthome/api/user/sip/getSipAccount"
        params = self._signed_query(extra_q)
        headers = self._headers()
        async with asyncio.timeout(10.0):
            async with session.get(url, params=params, headers=headers) as resp:
                self._capture_cookies(resp)
                resp_data = await resp.json()
                payload = self._extract_payload(resp_data)
                return dict(payload) if isinstance(payload, dict) else {}

    async def get_rtsp_config(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch RTSP video stream configuration for live preview."""
        session = await self._get_session()
        extra_q = {"deviceId": str(device_id)} if device_id else None
        url = f"{self._base_url}/smarthome/api/user/rtsp/auth/config"
        params = self._signed_query(extra_q)
        headers = self._headers()
        async with asyncio.timeout(10.0):
            async with session.get(url, params=params, headers=headers) as resp:
                self._capture_cookies(resp)
                resp_data = await resp.json()
                payload = self._extract_payload(resp_data)
                return dict(payload) if isinstance(payload, dict) else {}

    async def get_monitoring_list(self, device_id: str | int) -> List[Dict[str, Any]]:
        """Fetch indoor monitor camera/monitoring device list."""
        session = await self._get_session()
        url = f"{self._base_url}/smarthome/api/device/indoor/monitoring-list"
        params = self._signed_query({"deviceId": str(device_id)})
        headers = self._headers()
        async with asyncio.timeout(10.0):
            async with session.get(url, params=params, headers=headers) as resp:
                self._capture_cookies(resp)
                resp_data = await resp.json()
                payload = self._extract_payload(resp_data)
                if isinstance(payload, list):
                    return payload
                if isinstance(payload, dict):
                    return payload.get("list", payload.get("records", []))
                return []

    async def control_monitoring(
        self,
        device_id: str | int,
        monitoring_device_number: str = "001",
        action: int = 1,
        resolution_level: int = 0,
    ) -> Optional[str]:
        """Start (action=1) or stop (action=0) live video monitoring stream."""
        session = await self._get_session()
        url = f"{self._base_url}/smarthome/api/device-monitoring/monitoring"
        params = self._signed_query()
        data = {
            "action": action,
            "deviceId": str(device_id),
            "monitoringDeviceNumber": str(monitoring_device_number),
            "resolutionLevel": resolution_level,
        }
        headers = self._headers()
        async with asyncio.timeout(10.0):
            async with session.post(url, params=params, json=data, headers=headers) as resp:
                self._capture_cookies(resp)
                resp_data = await resp.json()
                payload = self._extract_payload(resp_data)
                if isinstance(payload, dict):
                    res = (
                        payload.get("callId")
                        or payload.get("call_id")
                        or payload.get("rtspUrl")
                        or payload.get("url")
                        or payload.get("streamUrl")
                        or payload.get("result")
                    )
                    return str(res).strip() if res is not None else None
                if isinstance(payload, (str, int)) and str(payload).strip():
                    return str(payload).strip()
                return None

    async def async_close(self) -> None:
        """Close client session if owned."""
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> "AveCloudApi":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.async_close()

