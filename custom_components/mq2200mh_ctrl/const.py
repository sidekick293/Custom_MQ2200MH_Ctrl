"""Constants for MQ2200MH Control integration."""

DOMAIN = "mq2200mh_ctrl"

DEFAULT_PORT = 502
DEFAULT_DEVICE_ID = 1
DEFAULT_SCAN_INTERVAL = 15

# Hard sanity bounds for power sensors.
# Readings outside [min, max] are discarded (the sensor keeps its last good
# value for that cycle). This catches garbage register reads that would
# otherwise show up as absurd spikes.
POWER_BOUNDS = {
    "total_pv_power": (0, 2500),
    "battery_power": (-3000, 3000),
    "active_power": (-100, 1500),
}

# FIFO median-style filter for slow/monotonic sensors (SOC + energy counters).
# Each cycle the raw reading is pushed into a buffer of length FIFO_LEN.
# Once at least FIFO_GROUP values are collected, the output is taken from the
# GROUP values that lie closest together (after sorting), using the newest of
# them. A lone spike therefore never wins, because it is far from every
# neighbour and gets excluded from the closest group.
FIFO_LEN = 5
FIFO_GROUP = 3

# Sensors that use the FIFO filter above.
FILTERED_SENSORS = {
    "battery_soc",
    "pv_total_energy",
    "battery_total_charge_energy",
    "battery_total_discharge_energy",
    "grid_total_export_energy",
    "grid_total_import_energy",
}
