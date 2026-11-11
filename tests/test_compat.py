import os
import json
import unittest
import compat_adapter

class TestCompatAdapter(unittest.TestCase):
    def setUp(self):
        self.orig_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.orig_env)

    def test_json_config_reading(self):
        test_users = [{
            "phone": "13800138000",
            "password": "password123",
            "province": "浙江省",
            "city": "台州市",
            "address": "浙江省台州市",
            "longitude": "121.420654",
            "latitude": "28.656386"
        }]
        os.environ["USER"] = json.dumps(test_users)
        res = compat_adapter.ensure_user_env()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["phone"], "13800138000")

    def test_legacy_env_conversion(self):
        if "USER" in os.environ:
            del os.environ["USER"]
        os.environ["PHONE"] = "13900139000"
        os.environ["PASSWORD"] = "mypassword"
        os.environ["PROVINCE"] = "浙江省"
        os.environ["CITY"] = "台州市"
        os.environ["ADDRESS"] = "浙江省台州市路桥区"
        os.environ["LONGITUDE"] = "121.420654"
        os.environ["LATITUDE"] = "28.656386"
        os.environ["SENDKEY"] = "SCT123456"

        res = compat_adapter.ensure_user_env()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["phone"], "13900139000")
        self.assertEqual(res[0]["password"], "mypassword")
        self.assertEqual(res[0]["province"], "浙江省")

        user_env_str = os.environ.get("USER")
        self.assertIsNotNone(user_env_str)
        loaded = json.loads(user_env_str)
        self.assertEqual(loaded[0]["phone"], "13900139000")

    def test_empty_config_handling(self):
        if "USER" in os.environ:
            del os.environ["USER"]
        if "PHONE" in os.environ:
            del os.environ["PHONE"]

        res = compat_adapter.ensure_user_env()
        self.assertEqual(res, [])

    def test_coordinate_validation(self):
        self.assertTrue(compat_adapter.validate_coordinates("121.420654", "28.656386"))
        self.assertFalse(compat_adapter.validate_coordinates("invalid", "28.656386"))
        self.assertFalse(compat_adapter.validate_coordinates("200.00", "28.656386"))
        self.assertFalse(compat_adapter.validate_coordinates("121.420654", "100.00"))

if __name__ == "__main__":
    unittest.main()
