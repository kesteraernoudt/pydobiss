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

# dobiss icon_id mapping
dobis_light = 0
dobis_plug = 1
dobis_ventilation = 2
dobis_up = 3
dobis_down = 4
dobis_heating = 5
dobis_tablelight = 6
dobis_door = 7
dobis_garage = 8
dobis_gate = 9
dobis_red = 10
dobis_green = 11
dobis_blue = 12
dobis_white = 13
dobis_inputstatus = 100
dobis_lightsensor = 101
dobis_scenario = 201
dobis_automation = 202
dobis_condition = 203
dobis_temperature = 204
dobis_audio = 205
dobis_flag = 206

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
		self._value = None
		self._dobiss = dobiss

	@property
	def name(self):
		"""Return the display name of this entity."""
		return self._name

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
					if self.address == dobis_temperature:
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
		if self._address == dobis_temperature:
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

class DobissSensor(DobissEntity):
	""" a dobiss sensor, can be binary or not, lightswitch, temperature sensor, etc """
	def __init__(self, dobiss, data, groupname):
		DobissEntity.__init__(self, dobiss, data, groupname)
		""" Initialize a DobissLight """
		if int(data["type"]) == dobis_temperature:
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

class DobissAPI:
	token = ''
	exp_time = datetime.now()
	
	def __init__(self, secret, url, ws_url):
		""" Initialize dobiss api object """
		self.secret = secret
		self.url = url
		self.ws_url = ws_url

	def get_token(self):
		""" Request a token to use in a request to the Dobiss server """
		if self.exp_time < datetime.now() + timedelta(hours=20):
			# get new token
			self.token = (jwt.encode({'name': 'my_application'}, self.secret, headers={'expiresIn': "24h" })).decode("utf-8")
			self.exp_time = datetime.now() + timedelta(hours=20)
		return self.token

	def discover(self):
		headers = { 'Authorization': 'Bearer ' + self.get_token() }
		return requests.get(self.url + 'discover', headers=headers)

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


	def get_dobiss_devices(self):
		entities = []
		response = self.discover()
		logger.debug("Discover response: {}".format(response))
		for group in response.json()["groups"]:
			for subject in group["subjects"]:
				logger.debug("Discovered {}: addr {}; channel {}; type {}; icon {}".format(subject["name"], subject["address"], subject["channel"], subject["type"], subject["icons_id"]))
				if group["group"]["id"] != 0:
					# skip first group - nothing of interest in there...
					if str(subject["icons_id"]) == "0": # check for lights
						entities.append(DobissLight(self, subject, group["group"]["name"]))
					elif str(subject["type"]) == "8": # other items connected to a relais
						entities.append(DobissSwitch(self, subject, group["group"]["name"]))
					elif str(subject["type"]) == "1": # status input
						entities.append(DobissSensor(self, subject, group["group"]["name"]))
					elif str(subject["type"]) == "206": # flags
						entities.append(DobissSwitch(self, subject, group["group"]["name"]))
					elif str(subject["type"]) == "201": # scenarios
						entities.append(DobissSwitch(self, subject, group["group"]["name"]))
					elif str(subject["type"]) == "202": # automations
						entities.append(DobissSwitch(self, subject, group["group"]["name"]))
					#elif str(subject["type"]) == "203": # logical conditions
					#	entities.append(DobissSensor(self, subject, group["group"]["name"]))
					elif (str(subject["type"]) == "204" and subject["name"] != "All zones"): # temperature
						entities.append(DobissSensor(self, subject, group["group"]["name"]))
					elif str(subject["type"]) == "0": # lightcell
						entities.append(DobissSensor(self, subject, group["group"]["name"]))
		return entities
	
	def update_from_status(self, status, entities):
		for e in entities:
			e.update_from_global(status)

	def update_all(self, entities):
		status = self.status().json()
		logger.debug("Status response: {}".format(status))
		for e in entities:
			e.update_from_global(status["status"])

	async def listen_for_dobiss(self, ws, entities):
		while True:
			response = await ws.recv()
			if response[0] == '{':
				self.update_from_status(json.loads(response), entities)

	async def dobiss_monitor(self, entities):
		websocket = await self.register_dobiss()
		asyncio.ensure_future(self.listen_for_dobiss(websocket, entities))

