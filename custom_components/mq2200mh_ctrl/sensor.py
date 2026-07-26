"""MQ2200MH sensor entities."""

import logging
from collections import deque
from itertools import count

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, UnitOfPower, UnitOfEnergy, PERCENTAGE
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FIFO_LEN, FIFO_GROUP, FILTERED_SENSORS
from .filters import despiked_value

_LOGGER = logging.getLogger(__name__)

SENSORS = [
    ("total_pv_power", "PV power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("active_power", "Active power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("battery_power", "Battery power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("battery_soc", "Battery SOC", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),
    ("pv_total_energy", "PV energy", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    ("battery_total_charge_energy", "Battery charge energy", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    ("battery_total_discharge_energy", "Battery discharge energy", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    ("grid_total_export_energy", "Grid export energy", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    ("grid_total_import_energy", "Grid import energy", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
]


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
    """Set up sensor platform from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    host = entry.data[CONF_HOST]

    entities = []
    for key, name, unit, device_class, state_class in SENSORS:
        cls = MQ2200MHFilteredSensor if key in FILTERED_SENSORS else MQ2200MHSensor
        entities.append(cls(coordinator, entry, host, key, name, unit, device_class, state_class))

    async_add_entities(entities)


class MQ2200MHSensor(CoordinatorEntity, SensorEntity):
    """A plain MQ2200MH sensor that keeps its last good value.

    Used for the power sensors, whose out-of-bounds readings are already
    dropped in the coordinator. If a cycle has no value for this key, the last
    good value is kept instead of going unavailable.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, host, key, name, unit, device_class, state_class):
        super().__init__(coordinator)
        self._key = key
        self._last_value = None
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"MQ2200MH ({host})",
            manufacturer="",
            model="MQ2200MH",
        )

    @property
    def native_value(self):
        if self.coordinator.data and self._key in self.coordinator.data:
            val = self.coordinator.data[self._key]
            self._last_value = round(val, 2) if isinstance(val, float) else val
        return self._last_value


class MQ2200MHFilteredSensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """A MQ2200MH sensor with a spike-rejecting FIFO filter.

    Each cycle the raw reading is pushed into a FIFO of length FIFO_LEN. Once
    the FIFO is completely full, the reported value is computed by
    despiked_value(): outliers are rejected and the newest survivor is used.
    A full buffer guarantees enough good neighbours to isolate a lone spike.

    While the FIFO is still warming up (fewer than FIFO_LEN readings, e.g. just
    after a restart), the value restored from Home Assistant's state database is
    reported instead of a raw, unfiltered reading. That way a spike in the first
    few cycles after a restart cannot leak through. With FIFO_LEN=5 and a 15 s
    scan interval this warm-up lasts about 75 s.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, host, key, name, unit, device_class, state_class):
        super().__init__(coordinator)
        self._key = key
        self._buffer = deque(maxlen=FIFO_LEN)
        self._seq = count()          # monotonically increasing sequence source
        self._last_value = None      # last reported (filtered / restored) value
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"MQ2200MH ({host})",
            manufacturer="",
            model="MQ2200MH",
        )

    async def async_added_to_hass(self):
        """Restore last known value so warm-up doesn't show unavailable/spikes."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (None, "unknown", "unavailable"):
            try:
                self._last_value = float(last.state)
            except (ValueError, TypeError):
                self._last_value = None

    def _push(self, value):
        """Add a raw reading to the FIFO with a fresh sequence number."""
        self._buffer.append((next(self._seq), value))

    @property
    def native_value(self):
        # Feed this cycle's raw reading (if any) into the FIFO.
        if self.coordinator.data and self._key in self.coordinator.data:
            self._push(self.coordinator.data[self._key])

        # Only filter once the FIFO is completely full. With a full buffer there
        # are always enough good neighbours to isolate a lone spike; filtering
        # earlier (e.g. with just FIFO_GROUP values) could let a spike win when
        # it has no good neighbours to be compared against. Until then we hold
        # the restored / last reported value rather than a raw reading.
        if len(self._buffer) >= FIFO_LEN:
            filtered = despiked_value(list(self._buffer), FIFO_GROUP)
            if filtered is not None:
                self._last_value = round(filtered, 2) if isinstance(filtered, float) else filtered

        return self._last_value
