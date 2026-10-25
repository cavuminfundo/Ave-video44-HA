"""Config flow and options flow for AVE Video V44 integration."""

import logging
from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_ACCOUNT,
    CONF_AUTH_METHOD,
    CONF_INTERCOM_BOOK,
    CONF_OTP,
    CONF_PASSWORD,
    CONF_PREFERRED_VIDEO_STREAM,
    CONF_UNLOCK_PULSE_DURATION,
    DEFAULT_INTERCOM_BOOK,
    DEFAULT_PREFERRED_VIDEO_STREAM,
    DEFAULT_UNLOCK_PULSE_DURATION,
    DOMAIN,
)
from .core.api import AveCloudApi

_LOGGER = logging.getLogger(__name__)

AUTH_METHOD_PASSWORD = "password"
AUTH_METHOD_OTP = "otp"


class AveVideo44ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AVE Video V44."""

    VERSION = 1

    def __init__(self) -> None:
        self._auth_method: str = AUTH_METHOD_PASSWORD
        self._account: Optional[str] = None
        self._homes: list = []

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """First step: choose authentication method."""
        if user_input is not None:
            method = user_input.get(CONF_AUTH_METHOD, AUTH_METHOD_PASSWORD)
            if method == AUTH_METHOD_OTP:
                return await self.async_step_otp_request()
            return await self.async_step_password()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_AUTH_METHOD, default=AUTH_METHOD_PASSWORD): vol.In([
                    AUTH_METHOD_PASSWORD,
                    AUTH_METHOD_OTP,
                ]),
            }),
        )

    async def async_step_password(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Password login step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            account = user_input[CONF_ACCOUNT]
            password = user_input[CONF_PASSWORD]
            session = None
            try:
                from homeassistant.helpers.aiohttp_client import async_get_clientsession
                session = async_get_clientsession(self.hass)
            except Exception:
                pass
            api = AveCloudApi(session=session)
            try:
                login_data = await api.login_with_password(account, password)
                if not login_data.get("token") and not login_data.get("sessionId"):
                    errors["base"] = "invalid_auth"
                else:
                    homes = await api.get_home_list()

                    home_id = homes[0].get("homeId") if homes else 1
                    home_name = homes[0].get("homeName", "Casa") if homes else "Casa"

                    unique_id = f"{account}_{home_id}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"{account} ({home_name})",
                        data={
                            CONF_ACCOUNT: account,
                            CONF_PASSWORD: password,
                            "token": login_data.get("token"),
                            "session_id": login_data.get("sessionId"),
                            "home_id": home_id,
                            "home_name": home_name,
                        },
                        options={
                            CONF_INTERCOM_BOOK: DEFAULT_INTERCOM_BOOK,
                            CONF_UNLOCK_PULSE_DURATION: DEFAULT_UNLOCK_PULSE_DURATION,
                            CONF_PREFERRED_VIDEO_STREAM: DEFAULT_PREFERRED_VIDEO_STREAM,
                        },
                    )
            except Exception as err:
                _LOGGER.warning("Authentication failed for %s: %s", account, err)
                errors["base"] = "invalid_auth"
            finally:
                await api.async_close()

        return self.async_show_form(
            step_id="password",
            data_schema=vol.Schema({
                vol.Required(CONF_ACCOUNT): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_otp_request(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Request OTP code for email address."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            self._account = user_input[CONF_ACCOUNT]
            session = None
            try:
                from homeassistant.helpers.aiohttp_client import async_get_clientsession
                session = async_get_clientsession(self.hass)
            except Exception:
                pass
            api = AveCloudApi(session=session)
            try:
                await api.request_otp(self._account)
                return await self.async_step_otp_verify()
            except Exception as err:
                _LOGGER.warning("OTP request failed for %s: %s", self._account, err)
                errors["base"] = "cannot_connect"
            finally:
                await api.async_close()

        return self.async_show_form(
            step_id="otp_request",
            data_schema=vol.Schema({
                vol.Required(CONF_ACCOUNT): str,
            }),
            errors=errors,
        )

    async def async_step_otp_verify(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Verify OTP code and create entry."""
        errors: Dict[str, str] = {}

        if user_input is not None and self._account:
            otp = user_input[CONF_OTP]
            session = None
            try:
                from homeassistant.helpers.aiohttp_client import async_get_clientsession
                session = async_get_clientsession(self.hass)
            except Exception:
                pass
            api = AveCloudApi(session=session)
            try:
                login_data = await api.login_with_otp(self._account, otp)
                if not login_data.get("token") and not login_data.get("sessionId"):
                    errors["base"] = "invalid_auth"
                else:
                    homes = await api.get_home_list()

                    home_id = homes[0].get("homeId") if homes else 1
                    home_name = homes[0].get("homeName", "Casa") if homes else "Casa"

                    unique_id = f"{self._account}_{home_id}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"{self._account} ({home_name})",
                        data={
                            CONF_ACCOUNT: self._account,
                            CONF_OTP: otp,
                            "token": login_data.get("token"),
                            "session_id": login_data.get("sessionId"),
                            "home_id": home_id,
                            "home_name": home_name,
                        },
                        options={
                            CONF_INTERCOM_BOOK: DEFAULT_INTERCOM_BOOK,
                            CONF_UNLOCK_PULSE_DURATION: DEFAULT_UNLOCK_PULSE_DURATION,
                            CONF_PREFERRED_VIDEO_STREAM: DEFAULT_PREFERRED_VIDEO_STREAM,
                        },
                    )
            except Exception as err:
                _LOGGER.warning("OTP verification failed for %s: %s", self._account, err)
                errors["base"] = "invalid_auth"
            finally:
                await api.async_close()

        return self.async_show_form(
            step_id="otp_verify",
            data_schema=vol.Schema({
                vol.Required(CONF_OTP): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create options flow handler."""
        return AveVideo44OptionsFlow(config_entry)


class AveVideo44OptionsFlow(config_entries.OptionsFlow):
    """Handle options for AVE Video V44."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return the config entry for this options flow."""
        if hasattr(self, "_config_entry") and self._config_entry is not None:
            return self._config_entry
        try:
            return super().config_entry
        except (AttributeError, TypeError):
            return getattr(self, "_config_entry", None)

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Manage user options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        entry = self.config_entry
        options = entry.options if entry else {}
        current_book = options.get(
            CONF_INTERCOM_BOOK,
            DEFAULT_INTERCOM_BOOK,
        )
        current_pulse = options.get(
            CONF_UNLOCK_PULSE_DURATION, DEFAULT_UNLOCK_PULSE_DURATION
        )
        current_stream = options.get(
            CONF_PREFERRED_VIDEO_STREAM, DEFAULT_PREFERRED_VIDEO_STREAM
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_INTERCOM_BOOK, default=current_book): str,
                vol.Optional(
                    CONF_UNLOCK_PULSE_DURATION, default=current_pulse
                ): int,
                vol.Optional(
                    CONF_PREFERRED_VIDEO_STREAM, default=current_stream
                ): vol.In(["sub_stream", "main_stream"]),
            }),
        )
