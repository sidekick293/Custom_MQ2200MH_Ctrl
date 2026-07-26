# HA Custom Component for MQ2200MH Ctrl

Home Assistant custom component for controlling Solar Battery MQ2200-M-H (aka Solakon One aka Avocado Orbit-M aka Avocado 22 Pro) via ModbusTCP.

## Installation

* Connect your MQ2200MH via cable or wifi to your home network.
* Ideally install via HACS (please search online if you do not know how).
* Go to 'Settings' -> 'Devices & Services' -> 'Add Integration', search for 'MQ2200MH Control', add it and input the IP address of your device.
* Add more integrations if you have several devices.

## Usage

Set a value for inverter export with the number entity 'Power control'. The set value resets itself an hour after the last update. The whole component is intended to regularly send updates to the battery, giving it a new value and following the demand somewhat dynamically.

Alongside the control, the component exposes sensors for PV power, AC power, battery power and state of charge, plus lifetime energy counters for PV, battery charge/discharge and grid import/export. The energy counters can be used directly in the Home Assistant Energy Dashboard.

## Things to be aware of

**The setpoint is not always honoured.** Two hardware limits override whatever you write.

When the battery is full (100%), the inverter might start feeding in more than initially was set. Do not be surprised to see more export than you asked for, because there is nowhere left to put the incoming PV power.

When the battery is at 10%, discharge should stop. The battery cannot be drained below that, so any setpoint you send is ignored until it charges back up.

Keep this in mind when building automations on top of the control entity. Treat the value you set as a request, not a guarantee, and read back the actual power sensors if you need to know what is really happening.

## Bogus readings and filtering

The MQ2200MH occasionally returns nonsense over Modbus. A single garbage reading can decode to something absurd, for example a battery charge of -23 GWh in one 15-second cycle. Left unchecked, one such spike can wreck a monthly energy statistic or make an automation misfire, so the component filters readings before reporting them.

The power sensors (PV, AC, battery power) use hard sanity bounds. A reading outside the configured range is discarded and the last good value is kept for that cycle.

SOC and the energy counters use a small FIFO buffer. Each cycle's reading goes into the buffer, and the reported value is derived from the readings that agree with each other, dropping any lone outlier. This needs no fixed thresholds, because the tolerance adapts to how big the sensor's own steps are.

The trade-off is a short warm-up delay after the component (re)starts. Until the FIFO buffer has filled, the sensor reports the value restored from Home Assistant's database rather than a raw, unfiltered reading. With the default settings this is about 75 seconds. Slightly delayed values are a better deal than a broken long-term statistic from a single spike.

All of this is tunable in `const.py`. You can adjust the power bounds (`POWER_BOUNDS`), the buffer length (`FIFO_LEN`), the number of readings that must agree (`FIFO_GROUP`), and which sensors are filtered (`FILTERED_SENSORS`). If a sensor still lets a spike through or reacts too slowly for your taste, change those values.

## Inner Workings

Based off the insights I got from other code and some freely available documents online, the component uses certain Modbus addresses to store information regarding how much power it is supposed to inject into your wall outlet or draw from it.

I limited the output to 800W.

Communication is plain socket code, no pymodbus or any other dependency.

Feel free to fork and change.

## License

MIT
