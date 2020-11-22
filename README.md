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

import logging

from time import sleep
import dobissapi

#dobissapi.logger.setLevel(logging.DEBUG)

secret = 'secret'
host = 'my_host'
secure = False

dobiss = dobissapi.DobissAPI(secret, host, secure)

async def main():

    if not await dobiss.auth_check():
        print("Error authenticating dobiss")
        return
    print("authenticated dobiss")

    asyncio.get_event_loop().create_task(dobiss.dobiss_monitor())

    entities = await dobiss.discovery()
    await dobiss.update_all()

    # check if caching works
    entities = await dobiss.discovery()

    # list scenarios
    scenarios = dobiss.get_devices_by_type(dobissapi.DobissScenario)
    for e in scenarios:
        print("{}: {}".format(e.object_id, e.json))

    # see if there are any buddies
    def test_covers(entities):
        for e in entities:
            if e.buddy:
                print(f"buddies found: {e.name} --> buddy {e.buddy.name}")

    test_covers(entities)


    def get_entity(entities, name):
        for e in entities:
            if e.name == name:
                return e

    # test updating and changing entities
    await get_entity(entities, "Mancave").update()
    await get_entity(entities, "Mancave").toggle()
    await asyncio.sleep(2)
    await get_entity(entities, "Mancave").toggle()

    # test callbacks
    def my_callback():
        print("callback happened")

    get_entity(entities, "Mancave").register_callback(my_callback)

    await asyncio.sleep(2)
    await get_entity(entities, "Mancave").turn_on()
    await asyncio.sleep(2)
    await get_entity(entities, "Mancave").turn_off()

    # check if new discovery works fine with old callback
    await asyncio.sleep(60)
    entities = await dobiss.discovery()
    await asyncio.sleep(2)
    await get_entity(entities, "Mancave").turn_on()
    await asyncio.sleep(2)
    await get_entity(entities, "Mancave").turn_off()

try:
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
except KeyboardInterrupt:
    print("Exiting")

```

## Author

Kester (kesteraernoudt@yahoo.com)

