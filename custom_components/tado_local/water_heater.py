import logging
from typing import Any, Dict

import aiohttp
from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature, PRECISION_TENTHS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, MANUFACTURER, format_model

_LOGGER = logging.getLogger(__name__)

OPERATION_HEAT = "heat"
OPERATION_OFF = "off"
OPERATION_AUTO = "auto"
OPERATION_LIST = [OPERATION_HEAT, OPERATION_AUTO, OPERATION_OFF]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up hot water entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    base_url = data["base_url"]

    entities = []
    for zone in coordinator.data.get("zones", []):
        if zone.get("zone_type") == "HOT_WATER":
            entities.append(TadoLocalHotWater(coordinator, zone, base_url))

    async_add_entities(entities)


class TadoLocalHotWater(CoordinatorEntity, WaterHeaterEntity):
    """Representation of a Tado Local hot water zone."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = (
        WaterHeaterEntityFeature.OPERATION_MODE | WaterHeaterEntityFeature.TARGET_TEMPERATURE
    )

    _attr_operation_list = OPERATION_LIST

    def __init__(self, coordinator, initial_data: Dict[str, Any], base_url: str) -> None:
        super().__init__(coordinator)
        self._zone_id = initial_data.get("zone_id") or initial_data.get("id")
        self._attr_name = initial_data.get("name", f"Hot Water {self._zone_id}")
        self._attr_unique_id = f"tado_local_hot_water_{self._zone_id}"
        self._base_url = base_url

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "hot_water", self._zone_id)},
            "name": self._attr_name,
            "manufacturer": MANUFACTURER,
            "model": format_model("hot_water"),
        }

    @property
    def _zone_state(self) -> Dict[str, Any]:
        for zone in self.coordinator.data.get("zones", []):
            zid = zone.get("zone_id") or zone.get("id")
            if zid == self._zone_id:
                return zone.get("state", zone) or {}
        return {}

    @property
    def _hw_state(self) -> Dict[str, Any]:
        return self._zone_state.get("hot_water", {})

    @property
    def current_operation(self) -> str:
        mode = self._hw_state.get("mode") or "auto"
        if mode == 0:
            return OPERATION_OFF
        if str(mode).lower() == "off":
            return OPERATION_OFF
        if str(mode).lower() in ("auto", "schedule", "smart_schedule"):
            return OPERATION_AUTO
        return OPERATION_HEAT

    @property
    def current_temperature(self):
        # Hot water typically only has target temp; current temp may not exist
        return None

    @property
    def target_temperature(self):
        return self._hw_state.get("target_temp_c")

    @property
    def min_temp(self):
        min_t = self._hw_state.get("min_temp_c")
        if min_t is None:
            return 30
        return min_t

    @property
    def max_temp(self):
        max_t = self._hw_state.get("max_temp_c")
        if max_t is None:
            return 80
        return max_t

    @property
    def supported_features(self):
        # Drop temperature feature if the zone does not support setting temp
        supports_temp = self._hw_state.get("supports_temperature")
        if supports_temp is False:
            return WaterHeaterEntityFeature.OPERATION_MODE
        return self._attr_supported_features

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._send_hot_water_update(mode=OPERATION_HEAT, temperature=temperature)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        await self._send_hot_water_update(mode=operation_mode)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send_hot_water_update(mode=OPERATION_HEAT)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send_hot_water_update(mode=OPERATION_OFF)

    async def _send_hot_water_update(self, mode: str, temperature: float | None = None):
        params = {"mode": mode}
        if temperature is not None and WaterHeaterEntityFeature.TARGET_TEMPERATURE in self.supported_features:
            params["temperature"] = str(temperature)

        url = f"{self._base_url}/hot_water/{self._zone_id}/set"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, params=params) as response:
                    if response.status != 200:
                        _LOGGER.error("Hot water update error: %s", await response.text())
                    else:
                        await self.coordinator.async_request_refresh()
            except Exception as err:
                _LOGGER.error("Connection error updating hot water: %s", err)
