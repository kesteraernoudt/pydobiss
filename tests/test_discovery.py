import sys
import types
import unittest


try:
    import aiohttp  # noqa: F401
except ModuleNotFoundError:
    aiohttp_stub = types.ModuleType("aiohttp")
    aiohttp_stub.ClientSession = object
    sys.modules["aiohttp"] = aiohttp_stub

try:
    import jwt  # noqa: F401
except ModuleNotFoundError:
    jwt_stub = types.ModuleType("jwt")
    jwt_stub.encode = lambda *args, **kwargs: "test-token"
    sys.modules["jwt"] = jwt_stub

from dobissapi.dobissapi import DOBISS_BLUE
from dobissapi.dobissapi import DOBISS_GREEN
from dobissapi.dobissapi import DOBISS_LIGHT
from dobissapi.dobissapi import DOBISS_PLUG
from dobissapi.dobissapi import DOBISS_RED
from dobissapi.dobissapi import DOBISS_TYPE_DALI
from dobissapi.dobissapi import DOBISS_TYPE_RELAIS
from dobissapi.dobissapi import DOBISS_WHITE
from dobissapi.dobissapi import DobissAPI
from dobissapi.dobissapi import DobissLight


def subject(
    name,
    address,
    channel,
    type_id=DOBISS_TYPE_DALI,
    icons_id=DOBISS_LIGHT,
    dimmable=True,
    **extra,
):
    data = {
        "name": name,
        "address": address,
        "channel": channel,
        "type": type_id,
        "icons_id": icons_id,
        "dimmable": dimmable,
    }
    data.update(extra)
    return data


def group(group_id, name, subjects):
    return {"group": {"id": group_id, "name": name}, "subjects": subjects}


def discovery(groups):
    return {"temp_calendars": [], "groups": groups}


class DiscoveryHandlingTest(unittest.TestCase):
    def setUp(self):
        self.api = DobissAPI("secret", "localhost", secure=False)

    def run_discovery(self, groups):
        with self.assertLogs("dobissapi.dobissapi", level="DEBUG") as logs:
            devices = self.api._get_dobiss_devices(discovery(groups))
        return devices, "\n".join(logs.output)

    def test_complete_rgbw_candidate_uses_group_zero_subchannels_as_metadata(self):
        devices, logs = self.run_discovery(
            [
                group(
                    1,
                    "Badkamer",
                    [
                        subject(
                            "Led badkamer",
                            address=5,
                            channel=4,
                            icons_id=DOBISS_RED,
                        )
                    ],
                ),
                group(
                    0,
                    "No group",
                    [
                        subject(
                            "Led badkamer groen",
                            address=5,
                            channel=5,
                            icons_id=DOBISS_GREEN,
                            tags=["rgbw"],
                        ),
                        subject(
                            "Led badkamer blauw",
                            address=5,
                            channel=6,
                            icons_id=DOBISS_BLUE,
                        ),
                        subject(
                            "Led badkamer wit",
                            address=5,
                            channel=7,
                            icons_id=DOBISS_WHITE,
                        ),
                        subject(
                            "No group relay",
                            address=7,
                            channel=0,
                            type_id=DOBISS_TYPE_RELAIS,
                            icons_id=DOBISS_PLUG,
                            dimmable=None,
                            settings={"debug": True},
                        ),
                    ],
                ),
            ]
        )

        self.assertEqual(["Led badkamer"], [device.name for device in devices])
        self.assertIsInstance(devices[0], DobissLight)
        self.assertIn("Raw discovered subject: group_id=0", logs)
        self.assertIn("tags=['rgbw']", logs)
        self.assertIn("settings={'debug': True}", logs)
        self.assertIn("RGB/RGBW candidate detected: kind=RGBW", logs)
        self.assertIn("used as RGB/RGBW candidate metadata", logs)
        self.assertIn("group 0 technical/no-group subject is not exposed", logs)

    def test_incomplete_rgb_candidate_is_logged_when_white_is_missing(self):
        devices, logs = self.run_discovery(
            [
                group(
                    2,
                    "Leefruimte",
                    [
                        subject(
                            "Led leefruimte",
                            address=5,
                            channel=8,
                            icons_id=DOBISS_RED,
                        )
                    ],
                ),
                group(
                    0,
                    "No group",
                    [
                        subject(
                            "Led leefruimte groen",
                            address=5,
                            channel=9,
                            icons_id=DOBISS_GREEN,
                        ),
                        subject(
                            "Led leefruimte blauw",
                            address=5,
                            channel=10,
                            icons_id=DOBISS_BLUE,
                        ),
                    ],
                ),
            ]
        )

        self.assertEqual(["Led leefruimte"], [device.name for device in devices])
        self.assertIn("RGB/RGBW candidate detected: kind=RGB", logs)
        self.assertIn("missing_optional=['white']", logs)
        self.assertIn("Led leefruimte groen", logs)
        self.assertIn("used as RGB/RGBW candidate metadata", logs)

    def test_group_zero_raw_outputs_are_not_added_as_normal_devices(self):
        devices, logs = self.run_discovery(
            [
                group(
                    0,
                    "No group",
                    [
                        subject(
                            "Loose relay",
                            address=8,
                            channel=1,
                            type_id=DOBISS_TYPE_RELAIS,
                            icons_id=DOBISS_PLUG,
                            dimmable=None,
                        )
                    ],
                )
            ]
        )

        self.assertEqual([], devices)
        self.assertIn("Skipping group 0 subject Loose relay", logs)
        self.assertIn("group 0 technical/no-group subject is not exposed", logs)

    def test_duplicate_address_channel_entries_in_non_zero_groups_are_merged(self):
        devices, logs = self.run_discovery(
            [
                group(
                    1,
                    "Kitchen",
                    [
                        subject(
                            "Kitchen light",
                            address=9,
                            channel=0,
                            icons_id=DOBISS_LIGHT,
                        )
                    ],
                ),
                group(
                    2,
                    "Evening",
                    [
                        subject(
                            "Kitchen light duplicate",
                            address=9,
                            channel=0,
                            icons_id=DOBISS_LIGHT,
                        )
                    ],
                ),
            ]
        )

        self.assertEqual(1, len(devices))
        self.assertEqual("Kitchen light duplicate", devices[0].name)
        self.assertIn("Duplicate raw address/channel discovered", logs)
        self.assertIn("Merged duplicate address/channel", logs)


if __name__ == "__main__":
    unittest.main()
