import voluptuous as vol
import aiohttp
import async_timeout
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_PORT,
)

async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> None:
    """Valida l'input utente tentando una connessione."""
    ip = data[CONF_IP_ADDRESS]
    port = data[CONF_PORT]
    
    # Tentiamo di connetterci all'endpoint /zones per verificare che il servizio risponda
    url = f"http://{ip}:{port}/zones"
    
    async with aiohttp.ClientSession() as session:
        async with async_timeout.timeout(5):
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception("Status code not 200")

class TadoLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestisce il flusso di configurazione per Tado Local."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Gestisce il passo iniziale dell'utente."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except Exception:
                # Mappa l'errore alla chiave in strings.json/translations
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Tado Local ({user_input[CONF_IP_ADDRESS]})",
                    data=user_input
                )

        data_schema = vol.Schema({
            vol.Required(CONF_IP_ADDRESS): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Required(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )