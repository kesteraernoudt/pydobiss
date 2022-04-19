# -*- coding: utf-8 -*-
import asyncio
import logging
from datetime import datetime
from datetime import timedelta

import aiohttp
import jwt

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)

DEF_DISCOVERY_INTERVAL = 60.0
MIN_DISCOVERY_INTERVAL = 10.0

# dobiss icon_id mapping
DOBISS_LIGHT = 0
DOBISS_PLUG = 1
DOBISS_VENTILATION = 2
DOBISS_UP = 3
DOBISS_DOWN = 4
DOBISS_HEATING = 5
DOBISS_TABLELIGHT = 6
DOBISS_DOOR = 7
DOBISS_GARAGE = 8
DOBISS_GATE = 9
DOBISS_RED = 10
DOBISS_GREEN = 11
DOBISS_BLUE = 12
DOBISS_WHITE = 13
DOBISS_INPUTSTATUS = 100
DOBISS_LIGHTSENSOR = 101
DOBISS_SCENARIO = 201
DOBISS_AUTOMATION = 202
DOBISS_CONDITION = 203
DOBISS_TEMPERATURE = 204
DOBISS_AUDIO = 205
DOBISS_FLAG = 206

ICON_FROM_DOBISS = {
    DOBISS_LIGHT: "mdi:lightbulb",
    DOBISS_PLUG: "mdi:power-plug",
    DOBISS_VENTILATION: "mdi:hvac",
    DOBISS_UP: "mdi:arrow-up",
    DOBISS_DOWN: "mdi:arrow-down",
    DOBISS_HEATING: "mdi:radiator",
    DOBISS_TABLELIGHT: "mdi:lamp",
    DOBISS_DOOR: "mdi:door",
    DOBISS_GARAGE: "mdi:garage",
    DOBISS_GATE: "mdi:gate",
    DOBISS_RED: "mdi:exclamation",
    DOBISS_GREEN: "mdi:thumb-up",
    DOBISS_BLUE: "mdi:help",
    DOBISS_WHITE: "mdi:alpha-n",
    DOBISS_INPUTSTATUS: "mdi:list-status",
    DOBISS_LIGHTSENSOR: "mdi:theme-light-dark",
    DOBISS_SCENARIO: "mdi:movie-open",
    DOBISS_AUTOMATION: "mdi:home-automation",
    DOBISS_CONDITION: "mdi:account-question",
    DOBISS_TEMPERATURE: "mdi:thermometer",
    DOBISS_AUDIO: "mdi:cast-audio",
    DOBISS_FLAG: "mdi:flag",
}

# DOBISS type mapping
DOBISS_TYPE_NXT = 0
DOBISS_TYPE_INPUT = 1
DOBISS_TYPE_DALI = 4
DOBISS_TYPE_RELAIS = 8
DOBISS_TYPE_ANALOG = 24
DOBISS_TYPE_SCENARIO = 201
DOBISS_TYPE_AUTOMATION = 202
DOBISS_TYPE_CONDITION = 203
DOBISS_TYPE_TEMPERATURE = 204
DOBISS_TYPE_AUDIO = 205
DOBISS_TYPE_FLAG = 206


class DobissEntity:
    """a generic Dobiss Entity, can be a light, switch, sensor, etc..."""

    def __init__(self, dobiss, data, groupname):
        """Initialize a DobissLight"""
        self._json = data
        self._attributes = dict()
        self._attributes["dobiss_group"] = groupname
        self._attributes.update(data)
        self._groupname = groupname
        self._name = data["name"]
        self._address = int(data["address"])
        self._channel = int(data["channel"])
        self._dimmable = bool(data["dimmable"])
        self._icons_id = int(data["icons_id"])
        self._type = int(data["type"])
        self._object_id = "dobissid_{}_{}".format(self._address, self._channel)
        self._value = None
        self._dobiss = dobiss
        self._callbacks = list()
        self._buddy = None

    def update_from_discovery(self, entity):
        self._json = entity.json
        self._groupname = entity.groupname
        self._name = entity.name
        self._dimmable = entity.dimmable
        self._icons_id = entity.icons_id
        self._type = entity.type
        self._attributes.update(entity.attributes)

    @property
    def buddy(self):
        """Buddies share the same name, and have an up/down icon"""
        return self._buddy

    @property
    def attributes(self):
        """Return all attributes of this entity"""
        return self._attributes

    def set_buddy(self, entity):
        self._buddy = entity

    @property
    def name(self):
        """Return the display name of this entity."""
        return self._name

    @property
    def object_id(self):
        """Return the object id of this entity."""
        return self._object_id

    @property
    def groupname(self):
        """Return the groupname of this entity."""
        return self._groupname

    @property
    def address(self):
        """Return the address of this entity."""
        return self._address

    @property
    def channel(self):
        """Return the channel of this entity."""
        return self._channel

    @property
    def json(self):
        """Return the json of this entity."""
        return self._json

    @property
    def dimmable(self):
        """Return the if this entity is dimmable."""
        return self._dimmable

    @property
    def value(self):
        """Return the value of the entity."""
        return self._value

    @property
    def icons_id(self):
        """Return the icons_id of this entity."""
        return self._icons_id

    @property
    def type(self):
        """Return the type of this entity."""
        return self._type

    @property
    def is_on(self):
        """Return true if entity is on."""
        return self._value is not None and self._value > 0

    def register_callback(self, callback):
        """Register callback, called when changes state."""
        self._callbacks.append(callback)

    def remove_callback(self, callback):
        """Remove previously registered callback."""
        self._callbacks.remove(callback)

    async def publish_updates(self):
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()

    # '204':
    # {
    #  '1': {'status': None, 'temp': '22.4', 'asked': None,
    #  'time': None, 'calendar': None, 'cooling_status': None,
    #  'cooling_asked': None, 'cooling_time': None},
    #  '2': {'status': None, 'temp': '6.1', 'asked': None,
    #  'time': None, 'calendar': None, 'cooling_status': None,
    #  'cooling_asked': None, 'cooling_time': None}
    # }

    async def push(self, status, force=False):
        """when an external status udate happened,
        and you want to update the internal value"""
        attributes = self._attributes
        if self.address == DOBISS_TEMPERATURE:
            try:
                val = float(status["temp"])
            except ValueError:
                val = None
            attributes = self._attributes.copy()
            attributes.update(status)
        else:
            if type(status) == dict:
                val = int(status["status"])
            else:
                val = int(status)
        if force or self._value != val or self._attributes != attributes:
            self._value = val
            self._attributes = attributes
            logger.debug(f"Updated {self._name} to {val} {self._attributes}")
            await self.publish_updates()

    async def update_from_global(self, status, force=False):
        """when an external status udate happened,
        and you want to update the internal value
         and parse the update data here to fetch what is needed"""
        try:
            if str(self.address) in status:
                line = status[str(self.address)]
                if type(line) == list and len(status[str(self.address)]) > self.channel:
                    await self.push(status[str(self.address)][self.channel], force)
                elif (
                    type(line) == dict
                    and str(self.channel) in status[str(self.address)]
                ):
                    await self.push(status[str(self.address)][str(self.channel)], force)
                # else:
                #    logger.debug(f"{self.name} not found in status update")
                # logger.debug("Updated {} = {}: groupname {}; addr {};
                #  channel {}; dimmable {}".format(self.name, self._value,
                #  self.groupname, self.address, self.channel, self.dimmable))
            # else:
            #    logger.debug("{} not found in update".format(self.name))
        except Exception:
            logger.exception("Error trying to update {}".format(self.name))

    async def update(self):
        """Fetch new state data for this entity.
        This is the only method that should fetch new data for Home Assistant.
        """
        response = await self._dobiss.status(self._address, self._channel)
        data = await response.json()
        await self.push(data["status"])


class DobissOutput(DobissEntity):
    """a generic Dobiss Output, can be a light, switch, etc..."""

    async def toggle(self):
        if self.is_on:
            await self.turn_off()
        else:
            await self.turn_on()

    async def turn_on(self, brightness=100, delayon=None, delayoff=None):
        """Instruct the entity to turn on.
        You can skip the brightness part if your entity does not support
        brightness control.
        """
        if self._dimmable:
            value = brightness
        else:
            value = 1
        await self._dobiss.action(
            self._address, self._channel, 1, value, delayon=delayon, delayoff=delayoff
        )

    async def turn_off(self):
        """Instruct the entity to turn off."""
        await self._dobiss.action(self._address, self._channel, 0)


class DobissLight(DobissOutput):
    """a dobiss light object, can be dimmable or not"""


class DobissAnalogOutput(DobissOutput):
    """a dobiss light object, can be dimmable or not"""


class DobissSwitch(DobissOutput):
    """a dobiss switch, can be up/down switch, door switch, etc..."""


class DobissScenario(DobissSwitch):
    """a dobiss scenario"""


class DobissAutomation(DobissSwitch):
    """a dobiss automation"""


class DobissFlag(DobissSwitch):
    """a dobiss flag"""


class DobissSensor(DobissEntity):
    """a dobiss sensor, can be binary or not,
    lightswitch, temperature sensor, etc"""

    def __init__(self, dobiss, data, groupname):
        super().__init__(dobiss, data, groupname)
        self._unit = None

    @property
    def unit(self):
        return self._unit

    def set_unit(self, unit):
        self._unit = unit


class DobissTempSensor(DobissSensor):
    """a dobiss Temperature Sensor"""

    def __init__(self, dobiss, data, groupname):
        super().__init__(dobiss, data, groupname)
        self._unit = "C"
        self._default_time = 30

    @property
    def asked(self):
        asked = self.attributes.get("asked")
        if asked is not None:
            return float(asked)
        return None

    @property
    def status(self):
        return self.attributes.get("status")

    @property
    def time(self):
        # from the dobiss NXT user interface:
        #  if time == -15 --> forever;
        #  if time == -30 --> calendar;
        #  else minutes
        return self.attributes.get("time")

    @property
    def calendar(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if "calendar" in self.attributes:
            calendar = self.attributes["calendar"]
            if self._dobiss.temp_calendars is not None:
                for cal in self._dobiss.temp_calendars:
                    if calendar == cal["id"]:
                        return cal["name"]
        return None

    @property
    def manual_mode(self):
        # time == -30 means automatic mode
        return self.time != -30

    @property
    def default_time(self):
        return self._default_time if self._default_time is not None else 30

    async def set_default_time(self, minutes=30):
        # dobiss default timer seems to be 30 minutes...
        if self._default_time != minutes:
            self._default_time = minutes
            await self.publish_updates()

    async def set_temperature(self, temp):
        # if we explicitly set a temperature,
        #  and the mode is currently auto, switch to manual mode
        time = self.time
        if not self.manual_mode:
            time = self.default_time
        await self.set_temp_timer(temperature=temp, minutes=time)

    async def set_manual_mode(self, manual=True):
        if manual:
            if not self.manual_mode:
                await self.set_temp_timer(minutes=self.default_time)
        else:
            await self.set_temp_timer(minutes=-30)

    async def set_preset_mode(self, preset_mode: str):
        id = None
        if self._dobiss.temp_calendars is not None:
            for cal in self._dobiss.temp_calendars:
                if preset_mode == cal["name"]:
                    id = cal["id"]
                    break
        if id is not None:
            await self._dobiss.action(self._address, self._channel, 110, id)

    async def set_timer(self, minutes):
        await self.set_temp_timer(minutes=minutes)

    async def set_temp_timer(self, temperature=None, minutes=None):
        if temperature is None:
            temperature = self.asked
        if temperature is None:
            temperature = 18
        if minutes is None:
            minutes = self.time
        if minutes is None:
            minutes = self.default_time
        # dobiss temperature request is (target-5)*10
        temperature = round((temperature - 5) * 10)
        action = 1
        # dobiss time period from 0-1425 minutes to 0-95 quarters (of an hour)
        # switch (time) {
        # case -15:
        # 	// Indefinite time
        # 	time = 0xFE;
        # 	break;
        # case -30:
        # 	// Reset to calendar
        # 	action = 0;
        # 	break;
        # default:
        # 	// Convert time to 15 minutes
        # 	time = time / 15;
        # 	break;
        time = 0
        if minutes == -15:
            # forever
            time = 0xFE
        elif minutes == -30:
            # reset to calendar
            action = 0
        else:
            time = round(minutes / 15)
        await self._dobiss.action(
            self._address, self._channel, action, temperature, time
        )


class DobissBinarySensor(DobissSensor):
    """a dobiss Binary Sensor"""


class DobissLightSensor(DobissSensor):
    """a dobiss Light Sensor"""

    def __init__(self, dobiss, data, groupname):
        super().__init__(dobiss, data, groupname)
        self._unit = "%"


class DobissAPI:
    def __init__(self, secret, host, secure: bool):
        """Initialize dobiss api object"""
        url = ""
        ws_url = ""
        if secure:
            url = f"https://{host}/api/local/"
            ws_url = f"wss://{host}/sockets/api"
        else:
            url = f"http://{host}/api/local/"
            ws_url = f"ws://{host}/sockets/api"

        self._host = host
        self._secure = secure
        self._token = ""
        self._exp_time = datetime.now()
        self._secret = secret
        self._url = url
        self._ws_url = ws_url
        self._last_discovery = None
        self._force_discovery = False
        self._discovery_interval = DEF_DISCOVERY_INTERVAL
        self._devices = []
        self._stop_monitoring = True
        self._callbacks = set()
        self._session = None
        self._temp_calendars = []

    @property
    def session(self):
        """The interval in seconds between 2 consecutive device discovery"""
        return self._session

    @property
    def host(self):
        return self._host

    @property
    def temp_calendars(self):
        return self._temp_calendars

    @property
    def calendars(self):
        calendars = []
        if self._temp_calendars is not None:
            for cal in self._temp_calendars:
                calendars.append(cal["name"])
        return calendars

    def start_session(self):
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(raise_for_status=True)
        return self._session

    async def end_session(self):
        if self._session:
            if not self.session.closed:
                await self._session.close()
            self._session = None
        return self._session

    async def auth_check(self):
        headers = {"Authorization": "Bearer " + self.get_token()}
        auth_ok = False
        try:
            self.start_session()
            async with self._session.get(
                self._url + "status", headers=headers
            ) as response:
                if response and response.status == 200:
                    auth_ok = True
        except Exception:
            logger.exception("Äuthenticating Dobiss failed")
        finally:
            await self._session.close()
        return auth_ok

    async def get_apikey(self):
        """Request the API key from dobiss NXT: need to enable this in the NXT server (blue button next to API key) first"""
        get_apikey_ok = False
        try:
            self.start_session()
            async with self._session.get(self._url + "jwtsecret") as response:
                if response and response.status == 200:
                    apikey_data = await response.json()
                    logger.debug(f"apikey response: {apikey_data}")
                    self._secret = apikey_data["jwt_secret"]
                    get_apikey_ok = True
        except Exception:
            logger.exception("Get APIKey Dobiss failed")
        finally:
            await self._session.close()
        return get_apikey_ok

    def get_token(self):
        """Request a token to use in a request to the Dobiss server"""
        if self._exp_time < datetime.now() + timedelta(hours=20):
            # get new token
            self._token = jwt.encode(
                {"name": "my_application"},
                self._secret,
                headers={"expiresIn": "24h"},
            )
            self._exp_time = datetime.now() + timedelta(hours=20)
        return self._token

    @property
    def discovery_interval(self):
        """The interval in seconds between 2 consecutive device discovery"""
        return self._discovery_interval

    @discovery_interval.setter
    def discovery_interval(self, val):
        if val < MIN_DISCOVERY_INTERVAL:
            raise ValueError(
                f"Discovery interval below {MIN_DISCOVERY_INTERVAL} seconds is invalid"
            )
        self._discovery_interval = val

    def _call_discovery(self):
        if not self._last_discovery or self._force_discovery:
            self._force_discovery = False
            return True
        difference = (datetime.now() - self._last_discovery).total_seconds()
        if difference > self._discovery_interval:
            return True
        return False

    # if discovery is called before that configured polling interval has passed
    # it return cached data retrieved by previous successful call
    async def discovery(self):
        if self._call_discovery():
            try:
                headers = {"Authorization": "Bearer " + self.get_token()}
                self.start_session()
                response = await self._session.get(
                    self._url + "discover", headers=headers
                )
                if response and response.status == 200:
                    discovered_devices = await response.json()
                    logger.debug(f"Discover response: {discovered_devices}")
                    self._get_dobiss_devices(discovered_devices)
            finally:
                self._last_discovery = datetime.now()
        else:
            logger.debug("Discovery: Use cached info")
        return self._devices

    async def status(self, address=None, channel=None):
        data = {}
        if address is not None:
            data["address"] = address
        if channel is not None:
            data["channel"] = channel
        headers = {"Authorization": "Bearer " + self.get_token()}
        self.start_session()
        return await self._session.get(self._url + "status", headers=headers, json=data)

    async def action(
        self,
        address,
        channel,
        action,
        option1=None,
        option2=None,
        delayon=None,
        delayoff=None,
    ):
        writedata = {"address": address, "channel": channel, "action": action}
        if option1 is not None:
            writedata["option1"] = option1
        if option2 is not None:
            writedata["option2"] = option2
        if delayon is not None:
            writedata["delayon"] = {}
            if delayon <= 120:
                writedata["delayon"]["value"] = delayon
                writedata["delayon"]["unit"] = "s"
            else:
                writedata["delayon"]["value"] = min(round(delayon / 60), 120)
                writedata["delayon"]["unit"] = "min"
        if delayoff is not None:
            writedata["delayoff"] = {}
            if delayoff <= 120:
                writedata["delayoff"]["value"] = delayoff
                writedata["delayoff"]["unit"] = "s"
            else:
                writedata["delayoff"]["value"] = min(round(delayoff / 60), 120)
                writedata["delayoff"]["unit"] = "min"
        logger.debug(f"Sending {writedata} to dobiss server")
        await self.request(writedata)

    async def request(self, data):
        """send a raw json request. According to the API docs, it should look like:
        {
            "address"   : VERPLICHT, adres van de module of het NXT actie adres (>200),
            "channel"   : VERPLICHT, module uitgang (start bij 0) of NXT uitgang nummer (start op 1),
            "action"    : VERPLICHT, actie id (0 = uit, 1 = aan, 2 = schakelen) // zie lijst van acties
            "option1"   : dimmer: waarde (0-100) / audio: volume (0-100) / temperatuur: stel temperatuur in of kalender
            "option2"   : dimmer: soft start/stop (0-254) / audio: bron / temperatuur: periode
            "delayon"   :
                {
                "value" : 0-120,
                "unit"  : "s","min"
                }
            "delayoff"  :
                {
                "value" : 0-120,
                "unit"  : "s","min"
                }
            "condition" :
                {
                "id"    : ID van de logische conditie die nagekeken moet worden voor de uitvoering,
                "operator": 'true' or 'false'
            }
        }
        """
        headers = {"Authorization": "Bearer " + self.get_token()}
        self.start_session()
        return await self._session.post(
            self._url + "action", headers=headers, json=data
        )

    def _get_dobiss_devices(self, discovered_devices):
        self._temp_calendars = discovered_devices["temp_calendars"]
        new_devices = []
        for group in discovered_devices["groups"]:
            for subject in group["subjects"]:
                logger.debug(
                    f"Group {group['group']['id']} Discovered {subject['name']}: addr {subject['address']}; \
                        channel {subject['channel']}; type {subject['type']}; icon {subject['icons_id']}"
                )
                if group["group"]["id"] != 0:
                    # skip first group - nothing here which is not visible in one of the other groups below
                    if str(subject["icons_id"]) == str(DOBISS_LIGHT) or str(
                        subject["icons_id"]
                    ) == str(
                        DOBISS_TABLELIGHT
                    ):  # check for lights
                        new_devices.append(
                            DobissLight(self, subject, group["group"]["name"])
                        )
                    elif str(subject["type"]) == str(
                        DOBISS_TYPE_ANALOG
                    ):  # other items connected to a 0-10V output
                        new_devices.append(
                            DobissAnalogOutput(self, subject, group["group"]["name"])
                        )
                    elif str(subject["type"]) == str(
                        DOBISS_TYPE_RELAIS
                    ):  # other items connected to a relais
                        new_devices.append(
                            DobissSwitch(self, subject, group["group"]["name"])
                        )
                    elif str(subject["type"]) == str(DOBISS_TYPE_INPUT):  # status input
                        new_devices.append(
                            DobissBinarySensor(self, subject, group["group"]["name"])
                        )
                    elif str(subject["type"]) == str(DOBISS_TYPE_FLAG):  # flags
                        new_devices.append(
                            DobissFlag(self, subject, group["group"]["name"])
                        )
                    elif str(subject["type"]) == str(DOBISS_TYPE_SCENARIO):  # scenarios
                        new_devices.append(
                            DobissScenario(self, subject, group["group"]["name"])
                        )
                    elif str(subject["type"]) == str(
                        DOBISS_TYPE_AUTOMATION
                    ):  # automations
                        new_devices.append(
                            DobissAutomation(self, subject, group["group"]["name"])
                        )
                    # elif str(subject["type"]) == "203": # logical conditions
                    # 	new_devices.append(DobissSensor(self, subject, group["group"]["name"]))
                    elif (
                        str(subject["type"]) == str(DOBISS_TYPE_TEMPERATURE)
                        and subject["name"] != "All zones"
                    ):  # temperature
                        new_devices.append(
                            DobissTempSensor(self, subject, group["group"]["name"])
                        )
                    elif str(subject["type"]) == str(
                        DOBISS_TYPE_NXT
                    ):  # lightcell or input contact
                        if str(subject["icons_id"]) == str(DOBISS_LIGHTSENSOR):
                            new_devices.append(
                                DobissLightSensor(self, subject, group["group"]["name"])
                            )
                        elif str(subject["icons_id"]) == str(DOBISS_INPUTSTATUS):
                            new_devices.append(
                                DobissBinarySensor(
                                    self, subject, group["group"]["name"]
                                )
                            )
                        # other things connected to dobiss NXT directly?? In demo there are screens etc
                        elif (
                            str(subject["icons_id"]) == str(DOBISS_UP)
                            or str(subject["icons_id"]) == str(DOBISS_DOWN)
                            or str(subject["icons_id"]) == str(DOBISS_GARAGE)
                            or str(subject["icons_id"]) == str(DOBISS_DOOR)
                            or str(subject["icons_id"]) == str(DOBISS_GATE)
                            or str(subject["icons_id"]) == str(DOBISS_VENTILATION)
                            or str(subject["icons_id"]) == str(DOBISS_HEATING)
                        ):
                            new_devices.append(
                                DobissSwitch(self, subject, group["group"]["name"])
                            )
        for dev in new_devices:
            existing_dev = self.get_device_by_id(dev.object_id)
            if existing_dev:
                existing_dev.update_from_discovery(dev)
            else:
                # a new device - add this to the list
                self._devices.append(dev)

        def get_buddy_name(s):
            buddy_pairs = [(" op", " neer"), (" open", " dicht")]
            for suffix, buddysuffix in buddy_pairs:
                if s.endswith(suffix):
                    buddyname = f"{s[:-len(suffix)]}{buddysuffix}"
                    return buddyname
            return s

        # search for buddies
        for device in self._devices:
            if device.icons_id == DOBISS_UP:
                # look for a corresponding buddy
                # starting from dobiss NXT 3.0, there is a lock field that points to the buddy
                if (
                    "settings" in device.attributes
                    and "locks" in device.attributes["settings"]
                    and device.attributes["settings"]["locks"] is not None
                ):
                    buddy_channel = device.attributes["settings"]["locks"][0]
                    for buddy in self._devices:
                        if (
                            buddy._channel == buddy_channel
                            and buddy._address == device._address
                        ):
                            buddy.set_buddy(device)
                            device.set_buddy(buddy)
                            logger.debug(f"buddy for {device.name} found")
                if device.buddy is None:
                    buddyname = get_buddy_name(device.name)
                    for buddy in self._devices:
                        if buddy.name == buddyname and buddy.icons_id == DOBISS_DOWN:
                            # we found a buddy
                            buddy.set_buddy(device)
                            device.set_buddy(buddy)
                            logger.debug(f"buddy for {device.name} found")
                if not device._buddy:
                    logger.warn(f"No buddy for {device.name} found")

        return self._devices

    def get_devices_by_type(self, dev_type):
        device_list = []
        for device in self._devices:
            if isinstance(device, dev_type):
                device_list.append(device)
        return device_list

    def get_all_devices(self):
        return self._devices

    def get_device_by_id(self, dev_id):
        for device in self._devices:
            if device.object_id == dev_id:
                return device
        return None

    async def update_from_status(self, status, force=False):
        for e in self._devices:
            await e.update_from_global(status, force)

    async def update_all(self, force=False):
        response = await self.status()
        status = await response.json()
        logger.debug("Status response: {}".format(status))
        await self.update_from_status(status["status"], force)

    async def listen_for_dobiss(self):
        while not self._stop_monitoring:
            logger.debug("registering for websocket connection")
            headers = {"Authorization": "Bearer " + self.get_token()}
            self.start_session()
            try:
                ws = await self._session.ws_connect(self._ws_url, headers=headers)
                while not self._stop_monitoring:
                    try:
                        response = await ws.receive_json()
                        # logger.debug("received ws message")
                        logger.debug(f"Status update pushed: {response}")
                        if response is not None:
                            await self.update_from_status(response)
                    except TypeError:
                        logger.exception("dobiss monitor exception")
                        if not ws.closed:
                            await ws.close()
                        break
                    except ValueError:
                        logger.exception("dobiss monitor exception")
                    except asyncio.exceptions.CancelledError:
                        logger.debug(
                            "websocket connection cancelled - we must be stopping"
                        )
                        self._stop_monitoring = True
                        break
                    except Exception:
                        logger.exception("Status update exception")
                        if not ws.closed:
                            await ws.close()
                        break
            except Exception:
                logger.exception("Failed to connect, waiting a bit before retrying")
                await asyncio.sleep(10)

    def stop_monitoring(self):
        self._stop_monitoring = True

    async def dobiss_monitor(self):
        self._stop_monitoring = False
        asyncio.ensure_future(self.listen_for_dobiss())
