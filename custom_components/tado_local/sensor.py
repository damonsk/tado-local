import logging
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER, format_model

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Configura i sensori Tado Local."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    
    entities = []
    
    # 1. Sensori Zona (Umidità, Temp Corrente, Temp Target)
    zones_data = coordinator.data.get("zones", [])
    for zone in zones_data:
        entities.append(TadoZoneHumidity(coordinator, zone))
        entities.append(TadoZoneCurrentTemp(coordinator, zone))
        entities.append(TadoZoneTargetTemp(coordinator, zone))

    # 2. Sensori Dispositivo (Numero di Serie)
    devices_data = coordinator.data.get("devices", [])
    for device in devices_data:
        entities.append(TadoDeviceSerial(coordinator, device))

    async_add_entities(entities)


class TadoZoneBaseSensor(CoordinatorEntity, SensorEntity):
    """Classe base per sensori di zona."""
    
    _attr_has_entity_name = True

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator)
        self._zone_id = zone_data.get("zone_id") or zone_data.get("id")
        self._zone_name = zone_data.get("name")
    
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "zone", self._zone_id)},
            "name": self._zone_name,
            "manufacturer": MANUFACTURER,
            "model": format_model("zone_control"),
        }

    def _get_zone_state(self):
        zones = self.coordinator.data.get("zones", [])
        for zone in zones:
            zid = zone.get("zone_id") or zone.get("id")
            if zid == self._zone_id:
                return zone.get("state", zone)
        return {}


class TadoZoneHumidity(TadoZoneBaseSensor):
    """Sensore di umidità."""
    
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "humidity"

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"tado_local_hum_{self._zone_id}"

    @property
    def native_value(self):
        return self._get_zone_state().get("hum_perc")


class TadoZoneCurrentTemp(TadoZoneBaseSensor):
    """Sensore Temperatura Corrente."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "current_temperature"

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"tado_local_cur_temp_{self._zone_id}"

    @property
    def native_value(self):
        return self._get_zone_state().get("cur_temp_c")


class TadoZoneTargetTemp(TadoZoneBaseSensor):
    """Sensore Temperatura Impostata (Target)."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "target_temperature"

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"tado_local_target_temp_{self._zone_id}"

    @property
    def native_value(self):
        return self._get_zone_state().get("target_temp_c")


class TadoDeviceSerial(CoordinatorEntity, SensorEntity):
    """Sensore seriale dispositivo."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "serial_number"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:barcode" 

    def __init__(self, coordinator, device_data):
        super().__init__(coordinator)
        self._device_id = device_data.get("device_id") or device_data.get("id")
        self._serial = device_data.get("serial_number")
        if not self._serial:
            self._serial = f"Unknown_{self._device_id}"
            
        self._attr_unique_id = f"tado_local_serial_{self._device_id}"
        
        via_device = None
        zone_id = device_data.get("zone_id")
        if zone_id:
            via_device = (DOMAIN, "zone", zone_id)
            
        raw_model = device_data.get("device_type", "Device")
        
        self._device_info_data = {
            "identifiers": {(DOMAIN, "device", self._device_id)},
            "name": f"Tado {self._serial}",
            "manufacturer": MANUFACTURER,
            "model": format_model(raw_model),
            "via_device": via_device,
            "serial_number": self._serial
        }

    @property
    def device_info(self):
        return self._device_info_data

    @property
    def native_value(self):
        devices = self.coordinator.data.get("devices", [])
        for dev in devices:
            did = dev.get("device_id") or dev.get("id")
            if did == self._device_id:
                return dev.get("serial_number", self._serial)
        return self._serial