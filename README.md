pydobiss Module Repository
==========================

## pydobiss

dobissapi is a lib that make you easier to use [dobiss's api](http://support.dobiss.com/books/nl-dobiss-nxt/page/developer-api).


## Install

```bash
pip install pydobiss
```

## Example

```python

import asyncio
from time import sleep
import dobissapi

secret = 'secret'
url = 'http://<ip>/api/local/'
ws_url = 'ws://<ip>/sockets/api'

dobiss = dobissapi.DobissAPI(secret, url, ws_url)
entities = dobiss.get_dobiss_devices()
dobiss.update_all(entities)

def get_entity(entities, name):
	for e in entities:
		if e.name == name:
			return e

get_entity(entities, "Mancave").update()
get_entity(entities, "Mancave").toggle()
sleep(2)
get_entity(entities, "Mancave").toggle()

async def my_app():
	await dobiss.dobiss_monitor(entities)

try:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(my_app())
    loop.run_forever()
except KeyboardInterrupt:
    print("Exiting")
```

## Author

Kester(kesteraernoudt@yahoo.com)

