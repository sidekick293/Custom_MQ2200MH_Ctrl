"""MQ2200MH power control number entity."""

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, UnitOfPower
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .modbus import write_registers, i32_to_registers

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
    """Set up number platform from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MQ2200MHPowerControl(entry, data)])


class MQ2200MHPowerControl(NumberEntity):
    """Slider for battery discharge power (0 to 800 W)."""

    _attr_has_entity_name = True
    _attr_name = "Power control"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_native_max_value = 800
    _attr_native_step = 10
    _attr_icon = "mdi:battery-charging"

    def __init__(self, entry, data):
        self._host = data["host"]
        self._port = data["port"]
        self._device_id = data["device_id"]
        self._value = 0
        self._attr_unique_id = f"{entry.entry_id}_power_control"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"MQ2200MH ({entry.data[CONF_HOST]})",
            manufacturer="",
            model="MQ2200MH",
        )

    @property
    def native_value(self):
        return self._value

    def set_native_value(self, value: float) -> None:
        """Handle slider change: write 4 registers to inverter."""
        power_watts = max(self._attr_native_min_value, min(self._attr_native_max_value, int(value)))

        if power_watts > 0:
            # AC discharge, PV priority (bit0=1, bit1=0, bits3:2=00)
            mode = 0x0001
        else:
            # Disabled
            mode = 0x0000

        power_regs = i32_to_registers(power_watts)
        values = [mode, 3600] + power_regs

        success = write_registers(self._host, self._port, 46001, values, self._device_id)

        if success:
            self._value = power_watts
            _LOGGER.info("MQ2200MH power set to %dW (mode=0x%04X)", power_watts, mode)
        else:
            _LOGGER.error("MQ2200MH power write failed")
