"""MQ2200MH Control - Home Assistant custom component."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, POWER_BOUNDS
from .modbus import read_registers, combine_i32, combine_u32

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up MQ2200MH Control from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    device_id = entry.data["device_id"]
    scan_interval = entry.data["scan_interval"]

    async def _async_update():
        return await hass.async_add_executor_job(_read_all, host, port, device_id)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_async_update,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "host": host,
        "port": port,
        "device_id": device_id,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def _in_bounds(key, value):
    """Return True if value is within the configured bounds for this sensor.

    Sensors without configured bounds always pass.
    """
    bounds = POWER_BOUNDS.get(key)
    if bounds is None:
        return True
    lo, hi = bounds
    if value < lo or value > hi:
        _LOGGER.warning(
            "%s reading %s out of bounds [%s, %s] - discarding", key, value, lo, hi
        )
        return False
    return True


def _read_all(host, port, device_id):
    """Read all sensor values (blocking, runs in executor thread)."""
    data = {}

    # PV power (39118, 2 registers, i32, W)
    regs = read_registers(host, port, 39118, 2, device_id)
    if regs and len(regs) >= 2:
        value = combine_i32(regs[0], regs[1])
        if _in_bounds("total_pv_power", value):
            data["total_pv_power"] = value

    # AC active power (39134, 2 registers, i32, W)
    regs = read_registers(host, port, 39134, 2, device_id)
    if regs and len(regs) >= 2:
        value = combine_i32(regs[0], regs[1])
        if _in_bounds("active_power", value):
            data["active_power"] = value

    # Battery power (39230, 2 registers, i32, W)
    regs = read_registers(host, port, 39230, 2, device_id)
    if regs and len(regs) >= 2:
        value = combine_i32(regs[0], regs[1])
        if _in_bounds("battery_power", value):
            data["battery_power"] = value

    # Battery SOC (39424, 1 register, i16, %)
    regs = read_registers(host, port, 39424, 1, device_id)
    if regs and len(regs) >= 1:
        soc = regs[0]
        if soc >= 0x8000:
            soc -= 0x10000
        data["battery_soc"] = soc

    # Energy block (39601, 10 registers)
    #   offset 0-1: pv total energy          (u32, /100 -> kWh)
    #   offset 2-3: (reserved)
    #   offset 4-5: battery charge energy    (u32, /100 -> kWh)
    #   offset 6-7: (reserved)
    #   offset 8-9: battery discharge energy (u32, /100 -> kWh)
    regs = read_registers(host, port, 39601, 10, device_id)
    if regs and len(regs) >= 10:
        data["pv_total_energy"] = combine_u32(regs[0], regs[1]) / 100
        data["battery_total_charge_energy"] = combine_u32(regs[4], regs[5]) / 100
        data["battery_total_discharge_energy"] = combine_u32(regs[8], regs[9]) / 100

    # Grid energy block (39621, 6 registers)
    #   offset 0-1: grid export energy (u32, /100 -> kWh)
    #   offset 2-3: (reserved)
    #   offset 4-5: grid import energy (u32, /100 -> kWh)
    regs = read_registers(host, port, 39621, 6, device_id)
    if regs and len(regs) >= 6:
        data["grid_total_export_energy"] = combine_u32(regs[0], regs[1]) / 100
        data["grid_total_import_energy"] = combine_u32(regs[4], regs[5]) / 100

    return data
