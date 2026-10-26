"""Config flow and options flow for AVE Video V44 integration."""

import logging
from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_ACCOUNT,
    CONF_AUTH_METHOD,
    CONF_ENABLE_AUDIO,
    CONF_INTERCOM_BOOK,
    CONF_OTP,
    CONF_PASSWORD,
    CONF_PREFERRED_VIDEO_STREAM,
    CONF_UNLOCK_PULSE_DURATION,
    CONF_ENABLE_SIDEBAR_PANEL,
    DEFAULT_ENABLE_AUDIO,
    DEFAULT_INTERCOM_BOOK,
    DEFAULT_PREFERRED_VIDEO_STREAM,
    DEFAULT_UNLOCK_PULSE_DURATION,
    DEFAULT_ENABLE_SIDEBAR_PANEL,
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
                            CONF_ENABLE_SIDEBAR_PANEL: DEFAULT_ENABLE_SIDEBAR_PANEL,
                            CONF_ENABLE_AUDIO: DEFAULT_ENABLE_AUDIO,
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
                            CONF_ENABLE_SIDEBAR_PANEL: DEFAULT_ENABLE_SIDEBAR_PANEL,
                            CONF_ENABLE_AUDIO: DEFAULT_ENABLE_AUDIO,
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
        """Manage user options or route to guided actions."""
        if user_input is not None:
            if "action" not in user_input:
                options = dict(self.config_entry.options) if self.config_entry else {}
                options.update(user_input)
                return self.async_create_entry(title="", data=options)
            action = user_input["action"]
            if CONF_ENABLE_AUDIO in user_input and self.config_entry:
                opts = dict(self.config_entry.options or {})
                opts[CONF_ENABLE_AUDIO] = user_input[CONF_ENABLE_AUDIO]
                self.config_entry.options = opts
            if action == "auto_discover":
                return await self.async_step_auto_discover()
            if action == "add_intercom":
                return await self.async_step_add_intercom()
            if action == "remove_intercom":
                return await self.async_step_remove_intercom()
            if action == "settings":
                return await self.async_step_settings()

        current_audio = DEFAULT_ENABLE_AUDIO
        if self.config_entry and self.config_entry.options:
            current_audio = self.config_entry.options.get(
                CONF_ENABLE_AUDIO,
                self.config_entry.data.get(CONF_ENABLE_AUDIO, DEFAULT_ENABLE_AUDIO)
                if self.config_entry.data else DEFAULT_ENABLE_AUDIO
            )
        elif self.config_entry and self.config_entry.data:
            current_audio = self.config_entry.data.get(CONF_ENABLE_AUDIO, DEFAULT_ENABLE_AUDIO)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action", default="auto_discover"): vol.In({
                    "auto_discover": "Scopri automaticamente interni e posti esterni (Auto-Discovery)",
                    "add_intercom": "Aggiungi interno alla rubrica",
                    "remove_intercom": "Rimuovi interno dalla rubrica",
                    "settings": "Impostazioni generali",
                }),
                vol.Optional(CONF_ENABLE_AUDIO, default=current_audio): bool,
            }),
        )

    async def async_step_auto_discover(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Auto-discover intercom and doorstation contacts from bus and cloud."""
        options = dict(self.config_entry.options) if self.config_entry else {}
        coordinator = None
        if self.config_entry:
            coordinator = getattr(self.config_entry, "runtime_data", None)
            if not coordinator and hasattr(self, "hass") and self.hass:
                coordinator = self.hass.data.get(DOMAIN, {}).get("entries", {}).get(self.config_entry.entry_id)

        discovered = {}
        if coordinator and hasattr(coordinator, "async_discover_intercoms"):
            discovered = await coordinator.async_discover_intercoms()

        # Parse existing contacts
        current_raw = options.get(CONF_INTERCOM_BOOK, "") or ""
        contacts_dict = {}
        for item in current_raw.split(","):
            item = item.strip()
            if "=" in item:
                c, n = item.split("=", 1)
                contacts_dict[c.strip()] = n.strip()

        # Merge discovered contacts
        contacts_dict.update(discovered)

        options[CONF_INTERCOM_BOOK] = ", ".join(f"{c}={n}" for c, n in sorted(contacts_dict.items()))
        if coordinator:
            coordinator.intercom_book = dict(contacts_dict)
            coordinator.update_intercom_book()

        return self.async_create_entry(title="", data=options)

    async def async_step_add_intercom(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Add an intercom contact to the phonebook."""
        if user_input is not None:
            code = user_input.get("intercom_code", "").strip()
            name = user_input.get("intercom_name", "").strip()
            options = dict(self.config_entry.options) if self.config_entry else {}
            current_raw = options.get(CONF_INTERCOM_BOOK, DEFAULT_INTERCOM_BOOK) or ""
            contacts = []
            for item in current_raw.split(","):
                item = item.strip()
                if "=" in item:
                    c, n = item.split("=", 1)
                    if c.strip() != code:
                        contacts.append((c.strip(), n.strip()))
            contacts.append((code, name))
            options[CONF_INTERCOM_BOOK] = ", ".join(f"{c}={n}" for c, n in contacts)
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="add_intercom",
            data_schema=vol.Schema({
                vol.Required("intercom_code"): str,
                vol.Required("intercom_name"): str,
            }),
        )

    async def async_step_remove_intercom(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Remove an intercom contact from the phonebook."""
        options = dict(self.config_entry.options) if self.config_entry else {}
        current_raw = options.get(CONF_INTERCOM_BOOK, DEFAULT_INTERCOM_BOOK) or ""
        contacts_dict = {}
        for item in current_raw.split(","):
            item = item.strip()
            if "=" in item:
                c, n = item.split("=", 1)
                contacts_dict[c.strip()] = f"{c.strip()} ({n.strip()})"

        if user_input is not None:
            remove_code = user_input.get("remove_code", "").strip()
            contacts = []
            for item in current_raw.split(","):
                item = item.strip()
                if "=" in item:
                    c, n = item.split("=", 1)
                    if c.strip() != remove_code:
                        contacts.append((c.strip(), n.strip()))
            options[CONF_INTERCOM_BOOK] = ", ".join(f"{c}={n}" for c, n in contacts)
            return self.async_create_entry(title="", data=options)

        schema = vol.Schema({
            vol.Required("remove_code"): vol.In(contacts_dict if contacts_dict else {"": "Nessun interno presente"}),
        })
        return self.async_show_form(step_id="remove_intercom", data_schema=schema)

    async def async_step_settings(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Manage general integration settings preserving phonebook."""
        entry = self.config_entry
        options = dict(entry.options) if entry else {}

        if user_input is not None:
            options[CONF_UNLOCK_PULSE_DURATION] = user_input.get(
                CONF_UNLOCK_PULSE_DURATION,
                options.get(CONF_UNLOCK_PULSE_DURATION, DEFAULT_UNLOCK_PULSE_DURATION),
            )
            options[CONF_PREFERRED_VIDEO_STREAM] = user_input.get(
                CONF_PREFERRED_VIDEO_STREAM,
                options.get(CONF_PREFERRED_VIDEO_STREAM, DEFAULT_PREFERRED_VIDEO_STREAM),
            )
            options[CONF_ENABLE_SIDEBAR_PANEL] = user_input.get(
                CONF_ENABLE_SIDEBAR_PANEL,
                options.get(CONF_ENABLE_SIDEBAR_PANEL, DEFAULT_ENABLE_SIDEBAR_PANEL),
            )
            options[CONF_ENABLE_AUDIO] = user_input.get(
                CONF_ENABLE_AUDIO,
                options.get(CONF_ENABLE_AUDIO, DEFAULT_ENABLE_AUDIO),
            )
            return self.async_create_entry(title="", data=options)

        current_pulse = options.get(
            CONF_UNLOCK_PULSE_DURATION, DEFAULT_UNLOCK_PULSE_DURATION
        )
        current_stream = options.get(
            CONF_PREFERRED_VIDEO_STREAM, DEFAULT_PREFERRED_VIDEO_STREAM
        )
        current_sidebar = options.get(
            CONF_ENABLE_SIDEBAR_PANEL, DEFAULT_ENABLE_SIDEBAR_PANEL
        )
        current_audio = options.get(
            CONF_ENABLE_AUDIO, DEFAULT_ENABLE_AUDIO
        )

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_UNLOCK_PULSE_DURATION, default=current_pulse
                ): int,
                vol.Optional(
                    CONF_PREFERRED_VIDEO_STREAM, default=current_stream
                ): vol.In(["sub_stream", "main_stream"]),
                vol.Optional(
                    CONF_ENABLE_SIDEBAR_PANEL, default=current_sidebar
                ): bool,
                vol.Optional(
                    CONF_ENABLE_AUDIO, default=current_audio
                ): bool,
            }),
        )
