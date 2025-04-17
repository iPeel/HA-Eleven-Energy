# Home Assistant Eleven Energy integration

Connects to your Eleven Energy site ( cloud connection ) and obtains minute by minute stats from your inverter. It also allows changing of the hybrid work mode through service calls.

## Installation

To use, add this repository through HACS and install the Eleven Energy Integration. You require HACS to be installed, follow the guide at [the HACS download site](https://www.hacs.xyz/docs/use/download/download/) for more details.

Install this integration into HACS, from the Code button above copy the Clone URL and then in the HACS section of Home Assistant, click the three dots in the top right corner, select "Custom Repositories" then paste in this repository URL. You can then search the HACS store for "Eleven Energy" to find and install this integration.

You will also need an API token obtained through the Site & System Settings page of the Eleven Energy app. Once you have a token, from the Devices page in Home Assistant, add an integration, choose "Eleven Energy" and add your API token when requested.

## Work Modes

The current Work Mode operating on each inverter is shown in the sensor.{device_id}_system_work_mode entity and is read only. To change work modes you can perform an Action ( Service Call in old money ) which allows you to specify additional attributes that control the work mode.

An action can be selected within an automation by selecting "Add action" then "Other actions" then "Perform an action", then select the appropriate service action from the list below. You can then select the device to perform the action on, or leave blank and the first Hybrid Inverter on the site will be used.

Each action may require parameters as specified below, to use a parameter, add it as a JSON object in the Action data, for example:

![image](https://github.com/user-attachments/assets/7509b544-0a29-4979-93be-702f736bdc90)


Available work modes are as follows:

### Self Consumption

This is the default work mode, with excess solar diverted to the battery by default, and the battery supplying local loads if needed.

To switch to thie work mode, use the "_set_work_mode_self_consumption_" service call with the following parameters:

Key | Required | Description
--- | --- | -----------
percent_to_battery | No | Sets the percentage of any excess solar that is diverted to the battery. For example as value of 50 will send half of the excess solar out to the grid and half into the battery.

### Force Charge

Charges the battery at a set power rate with energy from the grid. Once the target state of charge has been reached, the system will remain is a state where grid power is consumed to supply local loads until the work mode is changed.

To switch to thie work mode, use the "_set_work_mode_force_charge_" service call with the following parameters:

Key | Required | Description
--- | --- | -----------
target_power | Yes | The amount of power in kW to charge the battery at.
target_percent | Yes | The target State Of Charge to charge the battery up to, a value of 100 will fully charge the battery.

### Grid Export

Force discharges the battery and uses excess solar to export to the grid at the specified rate until the target State of Charge is reached, thereafter the system will export all excess solar until the work mode is changed.

To switch to thie work mode, use the "_set_work_mode_grid_export_" service call with the following optional parameters:

Key | Required | Description
--- | --- | -----------
target_power | Yes | The amount of power in kW to export to the grid, including excess solar and battery power.
target_percent | Yes | The target State Of Charge to discharge to.

### PV Export Priority

Exports all excess solar to the grid instead of charging the battery, if the amount of excess solar exceeds the export limit of the site then any excess is used to charge the battery.

To switch to thie work mode, use the "_set_work_mode_pv_export_" service call with no parameters.

### Idle Battery

Allows the system to "coast" without using any battery, useful if you would prefer to reserve battery capacity for an upcoming period of high cost import.

To switch to thie work mode, use the "_set_work_mode_idle_battery_" service call with the following parameters:

Key | Required | Description
--- | --- | -----------
allow_charging | No | Set to true if you still want to allow charging of the battery with excess solar i.e. only prohibit discharging.
allow_discharging | No | Set to true if you still want to allow discharging of the battery i.e. only prohibit charging.
