pydobiss Module Repository
==========================

## pydobiss

dobissapi is a python library that allows you to use [dobiss's api](http://support.dobiss.com/books/nl-dobiss-nxt/page/developer-api).


## Install

```bash
pip install pydobiss
```

## Example

```python

import asyncio
import logging

from time import sleep
import dobissapi

#dobissapi.logger.setLevel(logging.DEBUG)

secret = 'secret'
url = 'http://<ip>/api/local/'
ws_url = 'ws://<ip>/sockets/api'

dobiss = dobissapi.DobissAPI(secret, url, ws_url)
entities = dobiss.discovery()
dobiss.update_all()

# check if caching works
entities = dobiss.discovery()

# list scenarios
scenarios = dobiss.get_devices_by_type(dobissapi.DobissScenario)
for e in scenarios:
	print("{}: {}".format(e.object_id, e.json))

def get_entity(entities, name):
	for e in entities:
		if e.name == name:
			return e

# test updating and changing entities
get_entity(entities, "Mancave").update()
get_entity(entities, "Mancave").toggle()
sleep(2)
get_entity(entities, "Mancave").toggle()

try:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(dobiss.dobiss_monitor())
    loop.run_forever()
except KeyboardInterrupt:
    print("Exiting")
```

## Author

Kester (kesteraernoudt@yahoo.com)

