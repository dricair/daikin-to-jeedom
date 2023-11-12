#!/usr/bin/env python3

import unittest
import datetime
import json
from pathlib import Path
from daikin_to_jeedom import *


class Test(unittest.TestCase):
    def test_datetime_to_slot(self):
        self.assertEqual(datetime_to_slot(datetime.datetime(2023, 1, 1, 0, 0, 0),    True),  0)
        self.assertEqual(datetime_to_slot(datetime.datetime(2023, 1, 1, 2, 0, 0),    True),  1)
        self.assertEqual(datetime_to_slot(datetime.datetime(2023, 1, 1, 11, 59, 59), True),  5)
        self.assertEqual(datetime_to_slot(datetime.datetime(2023, 1, 1, 23, 59, 59), True),  11)
        self.assertEqual(datetime_to_slot(datetime.datetime(2023, 1, 1, 1, 00, 00),  False), 12)
        self.assertEqual(datetime_to_slot(datetime.datetime(2023, 1, 1, 2, 00, 00),  False), 13)
        self.assertEqual(datetime_to_slot(datetime.datetime(2023, 1, 1, 22, 00, 00), False), 23)

    def test_cumulate_power(self):
        power_data = list(range(24))

        self.assertEqual(cumulate_power(power_data,
                                        datetime.datetime(2023, 1, 1, 0, 0),
                                        datetime.datetime(2023, 1, 1, 2, 0)), (12, 13))
        self.assertEqual(cumulate_power(power_data,
                                        datetime.datetime(2023, 1, 1, 21, 10),
                                        datetime.datetime(2023, 1, 2, 0, 5)), (10 + 11, 12))

    def test_json_validate_str(self):
        self.assertEqual(json_validate_str('test', 1), "test: expecting a string")
        self.assertEqual(json_validate_str('test', ""), "test: string should not be empty")
        self.assertEqual(json_validate_str('test', "value"), None)

    def test_json_validate_dict(self):
        schema = {
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
        }

        self.assertEqual(json_validate_dict('root', "string", schema),
                         "root: a dict is required")
        self.assertEqual(json_validate_dict('root', {'username': 'username'}, schema),
                         "root: field 'password' is required")
        self.assertEqual(json_validate_dict('root', {'username': 1, 'password': 'password'}, schema),
                         "root/username: expecting a string")
        self.assertEqual(json_validate_dict('root', {'username': 'username', 'password': ''}, schema),
                         "root/password: string should not be empty")
        self.assertEqual(json_validate_dict('root', {'username': 'username', 'password': 'password'}, schema),
                         None)

        schema = {
            "type": "object",
            "properties": {
                "password": {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "string"
                        }
                    }
                }
            },
            "required": [
                "password"
            ]
        }

        self.assertEqual(json_validate_dict('root', {"password": "value"}, schema),
                         "root/password: a dict is required")
        self.assertEqual(json_validate_dict('root', {"password": {"value": 1}}, schema),
                         "root/password/value: expecting a string")
        self.assertEqual(json_validate_dict('root', {"password": {"value": "password"}}, schema),
                         None)


    def test_find_consumption_data(self):
        json_files = list(Path("fixtures").glob("*.json"))
        self.assertGreater(len(json_files), 0)

        for json_file in json_files:
            with json_file.open('r') as f:
                data = json.load(f)

            result = find_consumption_data(data)
            self.assertIsNotNone(result, f"File {json_file}: return None")
            self.assertTrue('/electrical' in result, f"File {json_file}: consumptionData does not contain '/electrical'")



if __name__ == "__main__":
    unittest.main()
