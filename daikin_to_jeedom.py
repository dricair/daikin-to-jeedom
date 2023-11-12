#! /usr/bin/env python3

from typing import Any, Optional, Dict, List, Callable, Union
import requests
import subprocess
import re
import json
import datetime
from pathlib import Path
import logging
import argparse

# Loaded from configuration file
conf = {}

JEEDOM_URL = "{JEEDOM_HOST}/core/api/jeeApi.php"
DAIKIN_SCRIPT = Path("daikin_data.js")
CONSUMPTION_DATA = "consumptionData"

CONF_SCHEMA = {
  "$schema": "http://json-schema.org/draft-04/schema#",
  "type": "object",
  "properties": {
    "jeedom": {
      "type": "object",
      "properties": {
        "api_key": {
          "type": "string"
        },
        "host": {
          "type": "string"
        }
      },
      "required": [
        "api_key",
        "host"
      ]
    },
    "daikin": {
      "type": "object",
      "properties": {
        "username": {
          "type": "string"
        },
        "password": {
          "type": "string"
        }
      },
      "required": [
        "username",
        "password"
      ]
    },
    "conf": {
      "type": "object",
      "properties": {
        "data_dir": {
          "type": "string"
        }
      },
      "required": [
        "data_dir"
      ]
    }
  },
  "required": [
    "jeedom",
    "daikin",
    "conf"
  ]
}


def json_validate_str(name: str, data: Any) -> Optional[str]:
    """
    Validate a non-empty string
    Return an error message if an error is found, None otherwise
    """
    if not isinstance(data, str):
        return f"{name}: expecting a string"
    if not data:
        return f"{name}: string should not be empty"
    return None


def json_validate_dict(name: str, data: Any, schema: Dict[str, Any]) -> Optional[str]:
    if not isinstance(data, dict):
        return f"{name}: a dict is required"

    for key in schema.get("required", []):
        if key not in data:
            return f"{name}: field '{key}' is required"

    for field, field_schema in schema["properties"].items():
        full_name = f"{name}/{field}"
        if field_schema["type"] == "object":
            message = json_validate_dict(full_name, data[field], field_schema)
        elif field_schema["type"] == "string":
            message = json_validate_str(full_name, data[field])
        else:
            message = f"{full_name}: unsupported type '{schema[field]['type']}'"

        if message is not None:
            return message

    for key in data.keys():
        if key not in schema['properties']:
            return f"{name}: field '{field}' not expected"

    return None


def read_configuration(conf_file: Path) -> None:
    """
    Read configuration from JSON file
    """
    global conf
    with conf_file.open() as f:
        data = json.load(f)

    message = json_validate_dict('root', data, CONF_SCHEMA)
    assert message is None, f"Error when reading file {conf_file}:\n{message}"

    conf = data


def jeedom_variable(name: str, value: Any = None, conv: Optional[Callable] = None, default: Any = None) -> Optional[Any]:
    """
    Read (value is None) or write (value not None) a variable on Jeedom

    args:
      name (str): Name of the variable
      value (Any): Value of the variable
      conv (Callable or None): Optional conversion function
      default (Any): default value if conversion fails

    returns:
      value (Any) for read, or None for write
    """
    payload = {
        'apikey': conf["jeedom"]["api_key"],
        'type': 'variable',
        'name': name
    }
    if value:
        payload['value'] = value

    if value is not None:
        logging.debug(f"Jeedom - write variable {name} with value {value}")
    r = requests.get(JEEDOM_URL.format(JEEDOM_HOST=conf["jeedom"]["host"]), params=payload)

    try:
        read_value = conv(r.text) if conv else r.text
    except ValueError:
        logging.debug(f"Conversion of value '{r.text}' failed, using default '{default}'")
        read_value = default

    if value is None:
        logging.debug(f"Jeedom - read variable {name} --> {read_value}")
    return read_value


def get_daikin_data() -> Dict[str, Any]:
    """
    Get data from Daikin. Each device is stored to a JSON file per ID
    """
    output_dir = Path(conf["conf"]["data_dir"])
    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    data = {}
    logging.debug(f"Daikin - Executing script {DAIKIN_SCRIPT}")
    p = subprocess.run(['node', str(DAIKIN_SCRIPT.resolve()), conf["daikin"]["username"], conf["daikin"]["password"]],
                       capture_output=True, encoding="utf-8", cwd=output_dir)

    re_output_file = re.compile("Output file: (.*)")
    for line in p.stdout.splitlines():
        m = re_output_file.match(line.rstrip())
        if m is not None:
            filename = output_dir / m.group(1)
            with filename.open() as f:
                data[filename.stem] = json.load(f)

    return data


def datetime_to_slot(date: datetime.datetime, yesterday: bool) -> int:
    """
    Convert a datetime to a slot. Each slot represents 2 hours, which makes 2
    hours per slot.

    0: yesterday from 0:00 to 2:00
    1: yesterday from 2:00 to 4:00
    ...
    12: today from 0:00 to 2:00
    ...
    23: today from 10:00 to 12:00

    args:
      date (datetime): date to check
      yesterday (bool): if true, report slot for yesterday, for today otherwise

    return:
      (int) Index of the slot (0-23)
    """
    return date.hour // 2 + (0 if yesterday else 12)


def cumulate_power(power_data: List[int], last_date: datetime.datetime, now: datetime.datetime) -> (float, float):
    """
    Cumulate power from previous data. If uses last value and last_date to know if it should
    cumulate.
    If datetime is more than 2 days ago, only cumulate with previous and current day

    args:
      power_data (List[int]): power data per hour for last 2 days
      last_date (datetime): last time data was saved
      now (datetime): current date and time

    returns:
      (float, float): (data to cumulate since last checkpoint, data for this slot)
    """
    current_slot = datetime_to_slot(now, False)
    assert last_date <= now
    if last_date.date() < (now - datetime.timedelta(days=1)).date():
        logging.warning("Last date is before yesterday - data is lost")
        last_slot = 0
    else:
        last_slot = datetime_to_slot(last_date, last_date.date() < now.date())

    logging.debug(f"Current slot: {current_slot}")
    logging.debug(f"Last slot: {last_slot}")

    cumulate = 0 if current_slot <= last_slot else sum(power_data[last_slot:current_slot])
    return (cumulate, power_data[current_slot])


def find_consumption_data(data: Union[Dict,List]) -> Optional[Dict]:
    """
    Recursively find consumption data independenty of the format. It can contain list or dicts.

    Args:
      data (List or Dict): Data from Daikin

    Return the Dict, or None if not found
    """
    if isinstance(data, list):
        for item in data:
            result = find_consumption_data(item)
            if result is not None:
                return result

    elif isinstance(data, dict):
        for key, value in data.items():
            if key == CONSUMPTION_DATA:
                return value
            elif isinstance(value, (dict, list)):
                result = find_consumption_data(value)
                if result is not None:
                    return result

    return None



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--conf", type=Path, default="conf.json", help="JSON configuration file")

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true")
    verbosity.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args()

    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.ERROR
    logging.basicConfig(format="%(asctime)s %(levelname)10s: %(message)s", datefmt='%Y-%m-%d %I:%M:%S', level=level)

    logging.debug(f"Reading configuration file {args.conf}")
    read_configuration(args.conf)

    """
    Update power from Daikin on Jeedom

    # Variables on Jeedom:
    # - <id>.commit_date: last commit date in ISO format
    # - <id>.cooling_current: cumulative power for cooling, including current slot
    # - <id>.cooling_commit: cumulative power for cooling, committed so not including current slot
    # - <id>.heating_current: cumulative power for heating, including current slot
    # - <id>.heating_commit: cumulative power for heating, committed so not including current slot
    """

    # Get power data from Daikin
    for key, data in get_daikin_data().items():
        consumption_data = find_consumption_data(data)['/electrical']

        now = datetime.datetime.now()
        names = {
            "commit_date": f"daikin.{key}.commit_date",
            "cooling_current": f"daikin.{key}.cooling_current",
            "cooling_commit": f"daikin.{key}.cooling_commit",
            "heating_current": f"daikin.{key}.heating_current",
            "heating_commit": f"daikin.{key}.heating_commit",
        }

        values = {}

        for name, jeedom_name in names.items():
            if "date" in name:
                values[name] = jeedom_variable(names[name], conv=datetime.datetime.fromisoformat,
                                               default=datetime.datetime.fromtimestamp(0))
            else:
                values[name] = jeedom_variable(names[name], conv=float, default=0)

        logging.debug(f"{key} - " + ", ".join([f"{key}: {val}" for key, val in values.items()]))

        cooling_update = cumulate_power(consumption_data["cooling"]["d"], values["commit_date"], now)
        heating_update = cumulate_power(consumption_data["heating"]["d"], values["commit_date"], now)

        logging.info(f"{key}: cooling update {values['cooling_commit']} + {cooling_update[0]} + {cooling_update[1]}")
        logging.info(f"{key}: heating update {values['heating_commit']} + {heating_update[0]} + {heating_update[1]}")

        values['commit_date'] = now.isoformat()
        values['cooling_commit'] = values['cooling_commit'] + cooling_update[0]
        values['cooling_current'] = values['cooling_commit'] + cooling_update[1]
        values['heating_commit'] = values['heating_commit'] + heating_update[0]
        values['heating_current'] = values['heating_commit'] + heating_update[1]
        for name, jeedom_name in names.items():
            jeedom_variable(jeedom_name, values[name])
