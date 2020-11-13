# -*- coding: utf-8 -*-

import jwt
import requests
import websockets
from datetime import datetime, timedelta
import asyncio
import json
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)

ATTR_BRIGHTNESS = "brightness"

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

class DobissEntity:
    """ a generic Dobiss Entity, can be a light, switch, sensor, etc... """

    def __init__(self, dobiss, data, groupname):
        """ Initialize a DobissLight """
        self._json = data
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
        """Return the value of the entity.	"""
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
        return self._value != None and self._value > 0

    def push(self, val):
        """when an external status udate happened, and you want to update the internal value"""
        if self._value != val:
            logger.info("Updated {} to {}".format(self.name, val))
            self._value = val
    
    def update_from_global(self, status):
        """when an external status udate happened, and you want to update the internal value and parse the update data here to fetch what is needed"""
        try:
            if str(self.address) in status:
                line = status[str(self.address)]
                if type(line) == list and len(status[str(self.address)]) > self.channel:
                    self.push(status[str(self.address)][self.channel])
                elif type(line) == dict and str(self.channel) in status[str(self.address)]:
                    if self.address == DOBISS_TEMPERATURE:
                        self.push(float(status[str(self.address)][str(self.channel)]['temp']))
                    else:
                        self.push(int(status[str(self.address)][str(self.channel)]))
                else:
                    logger.debug("{} not found in status update".format(self.name))
                logger.debug("Updated {} = {}: groupname {}; addr {}; channel {}; dimmable {}".format(self.name, self.value, self.groupname, self.address, self.channel, self.dimmable))
            else:
                logger.debug("{} not found in status update".format(self.name))
        except Exception:
            logger.exception("Error trying to update {}".format(self.name))

    def update(self):
        """Fetch new state data for this entity.
        This is the only method that should fetch new data for Home Assistant.
        """
        response = self._dobiss.status(self._address, self._channel)
        if self._address == DOBISS_TEMPERATURE:
            val = float(response.json()["status"]['temp'])
        else:
            val = int(response.json()["status"])
        self._value  = val

class DobissOutput(DobissEntity):
    """ a generic Dobiss Output, can be a light, switch, etc... """

    def toggle(self):
        if self.is_on:
            self.turn_off()
        else:
            self.turn_on()

    def turn_on(self, **kwargs):
        """Instruct the entity to turn on.
        You can skip the brightness part if your entity does not support
        brightness control.
        """
        if self._dimmable:
            self._value = kwargs.get(ATTR_BRIGHTNESS, 100)
        else:
            self._value = 1
        self._dobiss.action(self._address, self._channel, 1, self._value)

    def turn_off(self, **kwargs):
        """Instruct the entity to turn off."""
        self._value = 0
        self._dobiss.action(self._address, self._channel, 0)

class DobissLight(DobissOutput):
    """ a dobiss light object, can be dimmable or not """

class DobissSwitch(DobissOutput):
    """ a dobiss switch, can be up/down switch, door switch, etc... """

class DobissScenario(DobissSwitch):
    """ a dobiss scenario """

class DobissAutomation(DobissSwitch):
    """ a dobiss automation """

class DobissFlag(DobissSwitch):
    """ a dobiss flag """

class DobissSensor(DobissEntity):
    """ a dobiss sensor, can be binary or not, lightswitch, temperature sensor, etc """
    def __init__(self, dobiss, data, groupname):
        DobissEntity.__init__(self, dobiss, data, groupname)
        if int(data["type"]) == DOBISS_TEMPERATURE:
            self._unit = 'C'
        elif int(data["type"]) == 0:
            self._unit = '%'
        else:
            self._unit = None

    @property
    def unit(self):
        return self._unit
    
    def set_unit(self, unit):
        self._unit = unit

class DobissTempSensor(DobissSensor):
    """ a dobiss Temperature Sensor """

class DobissBinarySensor(DobissSensor):
    """ a dobiss Binary Sensor """

class DobissLightSensor(DobissSensor):
    """ a dobiss Light Sensor """

class DobissAPI:
    token = ''
    exp_time = datetime.now()
    
    def __init__(self, secret, url, ws_url):
        """ Initialize dobiss api object """
        self.secret = secret
        self.url = url
        self.ws_url = ws_url
        self._last_discovery = None
        self._force_discovery = False
        self._discovery_interval = DEF_DISCOVERY_INTERVAL
        self._devices = []
    
    def get_token(self):
        """ Request a token to use in a request to the Dobiss server """
        if self.exp_time < datetime.now() + timedelta(hours=20):
            # get new token
            self.token = (jwt.encode({'name': 'my_application'}, self.secret, headers={'expiresIn': "24h" })).decode("utf-8")
            self.exp_time = datetime.now() + timedelta(hours=20)
        return self.token

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
        if difference > self.discovery_interval:
            return True
        return False

    def discover_devices(self):
        devices = self.discovery()
        if not devices:
            return None
        return devices
        
    # if discovery is called before that configured polling interval has passed
    # it return cached data retrieved by previous successful call
    def discovery(self):
        if self._call_discovery():
            try:
                headers = { 'Authorization': 'Bearer ' + self.get_token() }
                response = requests.get(self.url + 'discover', headers=headers)
            finally:
                self._last_discovery = datetime.now()
            if response:
                result_code = response.status_code
                if result_code == 200:
                    discovered_devices = response.json()
                    logger.debug("Discover response: {}".format(discovered_devices))
                    self._get_dobiss_devices(discovered_devices)
        else:
            logger.debug("Discovery: Use cached info")
        return self._devices

    def status(self, address = None, channel = None):
        data = {}
        if address != None:
            data["address"] = address
        if channel != None:
            data["channel"] = channel
        #data = { 'address': address, 'channel': channel }
        headers = { 'Authorization': 'Bearer ' + self.get_token() }
        return requests.get(self.url + 'status', headers=headers, json=data)

    def action(self, address, channel, action, option1 = None):
        writedata = { 'address': address, 'channel': channel, 'action': action }
        if option1 != None:
            writedata["option1"] = option1
        headers = { 'Authorization': 'Bearer ' + self.get_token() }
        return requests.post(self.url + 'action', headers=headers, json=writedata)

    async def register_dobiss(self):
        headers = { 'Authorization': 'Bearer ' + self.get_token() }
        return await websockets.connect(self.ws_url, extra_headers=headers)

    def _get_dobiss_devices(self, discovered_devices):
        self._devices = []
        for group in discovered_devices["groups"]:
            for subject in group["subjects"]:
                logger.debug("Discovered {}: addr {}; channel {}; type {}; icon {}".format(subject["name"], subject["address"], subject["channel"], subject["type"], subject["icons_id"]))
                if group["group"]["id"] != 0:
                    # skip first group - nothing of interest in there...
                    if str(subject["icons_id"]) == "0": # check for lights
                        self._devices.append(DobissLight(self, subject, group["group"]["name"]))
                    elif str(subject["type"]) == "8": # other items connected to a relais
                        self._devices.append(DobissSwitch(self, subject, group["group"]["name"]))
                    elif str(subject["type"]) == "1": # status input
                        self._devices.append(DobissBinarySensor(self, subject, group["group"]["name"]))
                    elif str(subject["type"]) == "206": # flags
                        self._devices.append(DobissFlag(self, subject, group["group"]["name"]))
                    elif str(subject["type"]) == "201": # scenarios
                        self._devices.append(DobissScenario(self, subject, group["group"]["name"]))
                    elif str(subject["type"]) == "202": # automations
                        self._devices.append(DobissAutomation(self, subject, group["group"]["name"]))
                    #elif str(subject["type"]) == "203": # logical conditions
                    #	self._devices.append(DobissSensor(self, subject, group["group"]["name"]))
                    elif (str(subject["type"]) == "204" and subject["name"] != "All zones"): # temperature
                        self._devices.append(DobissTempSensor(self, subject, group["group"]["name"]))
                    elif str(subject["type"]) == "0": # lightcell
                        self._devices.append(DobissLightSensor(self, subject, group["group"]["name"]))
        return self._devices
    
    def get_devices_by_type(self, dev_type):
        device_list = []
        for device in self._devices:
            if type(device) == dev_type:
                device_list.append(device)
        return device_list

    def get_all_devices(self):
        return self._devices

    def get_device_by_id(self, dev_id):
        for device in self._devices:
            if device.object_id == dev_id:
                return device
        return None

    def update_from_status(self, status):
        for e in self._devices:
            e.update_from_global(status)

    def update_all(self):
        status = self.status().json()
        logger.debug("Status response: {}".format(status))
        for e in self._devices:
            e.update_from_global(status["status"])

    async def listen_for_dobiss(self, ws):
        while True:
            response = await ws.recv()
            if response[0] == '{':
                logger.debug("Status update pushed: {}".format(response))
                self.update_from_status(json.loads(response))

    async def dobiss_monitor(self):
        websocket = await self.register_dobiss()
        asyncio.ensure_future(self.listen_for_dobiss(websocket))

