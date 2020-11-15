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
import aiohttp

import sys
sys.path.insert(0, './pydobiss')

import logging

from time import sleep
import dobissapi

#dobissapi.logger.setLevel(logging.DEBUG)

secret = 'secret'
host = 'my_host'
secure = False

dobiss = dobissapi.DobissAPI(secret, host, secure)

async def main():

    entities = await dobiss.discovery()
    await dobiss.update_all()

    # check if caching works
    entities = await dobiss.discovery()

    # list scenarios
    scenarios = dobiss.get_devices_by_type(dobissapi.DobissScenario)
    for e in scenarios:
        print("{}: {}".format(e.object_id, e.json))

    def get_entity(entities, name):
        for e in entities:
            if e.name == name:
                return e

    # test updating and changing entities
    await get_entity(entities, "Mancave").update()
    await get_entity(entities, "Mancave").toggle()
    await asyncio.sleep(2)
    await get_entity(entities, "Mancave").toggle()

    #get_entity(entities, "Mancave").update()
    #get_entity(entities, "Mancave").turn_on()
    #sleep(2)
    #get_entity(entities, "Mancave").turn_off()

    def my_callback():
        print("callback happened")

    get_entity(entities, "Mancave").register_callback(my_callback)

try:
    loop = asyncio.get_event_loop()
    loop.create_task(dobiss.dobiss_monitor())
    loop.create_task(main())
    loop.run_forever()
except KeyboardInterrupt:
    print("Exiting")

```

## Author

Kester (kesteraernoudt@yahoo.com)

