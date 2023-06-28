# Daikin power to Jeedom

This simple scripts can be used in complement to
[Daikin Onecta plugin](https://market.jeedom.com/index.php?v=d&p=market_display&id=4183)
to get power data as the application permits. This script needs to be run regularly and
fills several variables to Jeedom, which can be used in virtuals.

## Disclaimer

**All product and company names or logos are trademarks™ or registered® trademarks of their
respective holders. Use of them does not imply any affiliation with or endorsement by them or
any associated subsidiaries! This personal project is maintained in spare time and has
no business goal.**

**Daikin is a trademark of DAIKIN INDUSTRIES, LTD.**


## Installation

The NPM package [daikin-controller-cloud](https://www.npmjs.com/package/daikin-controller-cloud)
is used to get the power data, like Daikin Onecta plugin.

To install the package:

    npm install

The `requests` Python package is required. You can install it either with `pip`:

    pip install requests

Or from Debian packages:

    sudo apt install python3-requests

This script requires Python >= 3.7

## Configuration

Copy the file `conf-template.json` to `conf.json`, and edit it. Required fields are:

- `jeedom/api_key`: Jeedom API key which can be found in System -> Configuration -> API
  (You need to make it visible by clicking on the button)
- `jeedom/host`: Host on which Jeedom is accessible. If the script runs on the same
  machine as Jeedom, you can just use `http://127.0.0.1`. It can also be a address on the
  same network like `http://192.168.0.22`, or an external HTTP/HTTPS address.
- `daikin/username` and `daikin/password`, same as the Daikin Cloud application
- `conf/data-dir`, by default `daikin-data`

Try running the script to check configuration. In case of error, check the `conf.json` file:

    python3 daikin_to_jeedom.py -v

This should create a `daikin-data` directory containing dumped data
from all components found on the cloud application.

## Regular runs of the script

The script needs to be regularly run to report consumption to Jeedom variables. It can typically run as a cron job every hour or every day. It is best to not run at exact hour due to the way data is
encoded from Daikin Cloud, as it would cause glitches and may loose
data.

To setup cron:

    crontab -e

Then to run every hour, add this line (Replace `<dir>` by the clone
directory):

    55 * * * * cd <dir> && python3 ./daikin_to_jeedom.py

## Integration with Jeedom

The script creates variables with an ID corresponding to the Daikin
ID. Variables useful for Jeedom are:

- `daikin.<ID>.cooling_current`: Cumulative consumption (in kWh)
  when device is in cooling mode.
- `daikin.<ID>.heating_current`: Cumulative consumption (in kWh)
  when device is in heating mode.

Some other variables are defined but should only be used by the
script to calculate previous variables:

- `daikin.<ID>.commit_date`: as consumption is per hour, commit date
  corresponds to the date/time for the hour previous to the
  script run. Current hour is used as well but only in `current`.
- `daikin.<ID>.cooling_commit`: cumulated consumption when device is
  in cooling mode. It does not include consumption for the current
  hour.
- `daikin.<ID>.heating_commit`: cumulated consumption when device is
  in heating mode. It does not include consumption for the current
  hour.

Note: some variables may not exist if value is 0.

You need to link `<ID>` to your devices. If you are using the Daikin
Onecta plugin, you can get ID for each by clicking on the equipment
and "Advanced configuration". This is show as "Logical ID".

Cumulative consumption data can be converted to consumption per hour
or per day by creating a scenario. For example a scenario triggered
every hour, so programmed trigger is:

    0 * * * *

Then in the scenario you can create an action block containing
several actions. For example:

| Type       | Name           | Value              |
| ---------- | -------------  | --------           |
| variable   | `Daikin1Conso` | `variable(daikin.<ID>.cooling_current) - variable(Daikin1Prev)` |
| variable   | `Daikin1Prev`  | `variable(daikin.<ID>.cooling_current)` |

You can use variable `Daikin1Conso` in a virtual and enable history.


