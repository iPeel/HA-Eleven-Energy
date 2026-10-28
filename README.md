# Home Assistant Eleven Energy integration

<a href="https://www.elevenenergy.co.uk"><img src="https://brands.home-assistant.io/eleven_energy/dark_logo.png" width="300px" alt="Eleven Energy website"/></a>

Connects to your Eleven Energy site ( cloud connection ) and obtains minute by minute stats from your inverter, including per phase, per battery and per solar string detail. It also allows the hybrid work mode to be changed from an automation.

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/iPeel/HA-Eleven-Energy)
![Project Maintenance][maintenance-shield]
[![GitHub Activity][commits-shield]][commits]

![image](https://github.com/user-attachments/assets/03d5442b-45a8-466d-b946-a090bafffff7)


## Installation

To use, add this repository through HACS and install the Eleven Energy Integration. You require HACS to be installed, follow the guide at [the HACS download site](https://www.hacs.xyz/docs/use/download/download/) for more details.

Once HACS is installed on your system:

* [Add the Eleven Energy repository](https://my.home-assistant.io/redirect/hacs_repository/?owner=iPeel&repository=HA-Eleven-Energy&category=integration) to your HACS installation
* Click `Download`

Then, from the Devices page in Home Assistant, add an integration and choose "Eleven Energy". You will be offered two ways to connect:

* **Sign in with Eleven Energy** - you are sent to the Eleven Energy site to log in and approve the connection, and Home Assistant is given its own credentials. Nothing is typed into Home Assistant, the connection is named so you can recognise it later, and you can withdraw it at any time from Site & System Settings in the Eleven Energy app. This is the recommended option.
* **Use an API token** - paste a token obtained through the Site & System Settings page of the Eleven Energy app, as in previous releases.

Existing installations keep working exactly as they are. If you would like to move an API token installation over to signing in, choose `Reconfigure` from the integration's menu and pick the other option; your entities, their ids and your automations are untouched.

## What you get

A device is created for each hybrid inverter on your site, named for its model, with the following entities.

Always present:

State Of Charge, PV Power, PV Energy Today, Consumed Today, Consumption, Battery Power, Charged Today, Discharged Today, Imported Today, Exported Today, Grid Power, System Power, System Voltage, Work Mode, Status, Online, Rated AC Power, Rated DC Power.

Per solar string ( MPPT ), as diagnostics - two on a single battery system, three on a dual battery system:

MPPT *n* Power, MPPT *n* Voltage, MPPT *n* Current.

On a three phase inverter, per phase:

Grid Power L*n*, Grid Voltage L*n*, Grid Current L*n*, System Power L*n*, System Voltage L*n*, System Current L*n*.

The existing whole system figures are unchanged on three phase machines - System Power and Grid Power remain the total across all three phases, so anything you have already built keeps reading what it always did.

On a dual battery system, per battery, as diagnostics:

Battery *n* Power, Battery *n* Modules, Battery *n* Raw State Of Charge.

The two batteries are reported separately because each has its own BMS and they do not necessarily track one another. The headline State Of Charge remains the figure the system manages against.

## Controlling your inverter

Setting any work mode switches off the Eleven Energy optimiser for that site, and it stays switched off until you send `Reset Work Mode`. Automations that take control should hand it back when they are done.

### Actions

In an automation, choose `Add action` and find the work mode under `Eleven Energy` - by searching for it, or under `By type`. Each one takes its parameters as proper form fields: sliders, kW boxes and switches.

![image](https://github.com/user-attachments/assets/7509b544-0a29-4979-93be-702f736bdc90)

Every work mode takes an optional **Inverter**. Leave it alone and the only hybrid inverter on the site is used, which is what the automations most people have written already do. Set it where a site has two, or the action may reach the wrong machine.

The parameters are listed with each work mode below. The name shown is the label in the user interface; the key is what you write if you are editing the action in YAML.

Note that the work modes are not listed under the inverter itself in `By target`. Home Assistant no longer permits an action to name a device as its target, so nothing associates them with a particular machine until you choose one in the Inverter field.

### Device actions

On Home Assistant versions whose automation editor offers them, the same work modes also appear as device actions once you have picked an inverter. They delegate to the actions above, so the two are interchangeable and anything written with either keeps working. Newer versions do not ask integrations for device actions in the automation editor, so you may not see them.

## Work Modes

The work mode currently running on each inverter is shown in the `sensor.{device_id}_system_work_mode` entity and is read only.

### Self Consumption

This is the default work mode, with excess solar diverted to the battery by default, and the battery supplying local loads if needed.

The "_set_work_mode_self_consumption_" action, or the "Self Consumption" device action where your version of Home Assistant offers them.

Name | Key | Required | Description
--- | --- | --- | -----------
Percentage To Battery | percent_to_battery | No | Sets the percentage of any excess solar that is diverted to the battery. For example a value of 50 will send half of the excess solar out to the grid and half into the battery.

### Grid Charge

Charges the battery at a set power rate with energy from the grid. Once the target state of charge has been reached, the system will remain in a state where grid power is consumed to supply local loads until the work mode is changed.

The "_set_work_mode_force_charge_" action, or the "Grid Charge" device action where your version of Home Assistant offers them.

Name | Key | Required | Description
--- | --- | --- | -----------
Target Power | target_power | Yes | The amount of power in kW to charge the battery at.
Target SoC % | target_percent | Yes | The target State Of Charge to charge the battery up to, a value of 100 will fully charge the battery.

### Grid Export

Force discharges the battery and uses excess solar to export to the grid at the specified rate until the target State of Charge is reached, thereafter the system will export all excess solar until the work mode is changed.

The "_set_work_mode_grid_export_" action, or the "Grid Export" device action where your version of Home Assistant offers them.

Name | Key | Required | Description
--- | --- | --- | -----------
Target Power | target_power | Yes | Battery discharge power in kW. This is battery power, not power at the meter: with 1 kW of house load, 5 kW here puts about 4 kW on the grid.
Target SoC % | target_percent | Yes | The target State Of Charge to discharge to.
Add Surplus Solar | include_excess_solar | No | Export surplus solar on top of the discharge power rather than storing it, useful when ensuring the battery is discharged to a specified level.
Overdrive | overdrive | No | Allow exceeding the usual export ceiling where the connection permits it. Leave off unless you have been told otherwise.

### Excess PV Export

Exports all excess solar to the grid instead of charging the battery. If the amount of excess solar exceeds the export limit of the site then any excess is used to charge the battery.

The "_set_work_mode_pv_export_" action, which takes no parameters, or the "Excess PV Export" device action where your version of Home Assistant offers them.

### Target State Of Charge

Manages grid export, battery charging and battery discharging based on a specified target state of charge and duration. The energy management system will then attempt to balance the amount of excess solar and battery to reach the specified state of charge by the end of the period, using an average of solar excess and available battery. A higher or lower state of charge goal may be specified than the current state of charge, however the system will not force charge from the grid to reach a higher state of charge goal, only using excess solar to charge the battery.

To avoid target charging and export power reaching infinity or excessive values, the algorithm tops out at 30 minutes remaining. I.e. if the work mode stays in Target SoC mode or reaches within 30 minutes of the target period, the algorithm treats all calculations as if there are 30 minutes remaining to reach the target.

The "_set_work_mode_target_soc_" action, or the "Target State Of Charge" device action where your version of Home Assistant offers them.

Name | Key | Required | Description
--- | --- | --- | -----------
Target SoC % | target_soc | Yes | The desired state of charge in percent to reach at the end of the period.
Target Minutes | target_minutes | Yes | The number of minutes from initiating this command to reach the target state of charge by.
Max Charge Power | max_charge_power | No | The amount of kilowatts max to charge the battery at. Defaults to the maximum charge rate of the battery.
Max Discharge Power | max_discharge_power | No | The amount of kilowatts max to discharge the battery at. Defaults to the maximum discharge rate of the battery.

### Idle Battery

Allows the system to "coast" without using any battery, useful if you would prefer to reserve battery capacity for an upcoming period of high cost import.

The "_set_work_mode_idle_battery_" action, or the "Idle Battery" device action where your version of Home Assistant offers them.

Name | Key | Required | Description
--- | --- | --- | -----------
Allow Charging | allow_charging | No | Set to true if you still want to allow charging of the battery with excess solar i.e. only prohibit discharging.
Allow Discharging | allow_discharging | No | Set to true if you still want to allow discharging of the battery i.e. only prohibit charging.

### Reset Work Mode

Restores the system's own operation. If a schedule was in effect when the mode was changed it resumes, otherwise automatic operation does.

The "_set_work_mode_reset_" action, which takes no parameters, or the "Reset Work Mode" device action where your version of Home Assistant offers them.




[commits-shield]: https://img.shields.io/github/commit-activity/y/iPeel/HA-Eleven-Energy.svg?style=for-the-badge
[commits]: https://github.com/iPeel/HA-Eleven-Energy/commits/master
[devcontainer]: https://code.visualstudio.com/docs/remote/containers
[license-shield]: https://img.shields.io/github/license/iPeel/HA-Eleven-Energy.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/iPeel/HA-Eleven-Energy.svg?style=for-the-badge
[releases]: https://github.com/iPeel/HA-Eleven-Energy/releases
