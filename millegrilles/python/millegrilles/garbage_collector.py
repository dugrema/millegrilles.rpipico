import uasyncio as asyncio
import gc

from micropython import mem_info


async def garbage_collection_thread():
    while True:
        await garbage_collection_update()
        await asyncio.sleep(60)


CONST_MEM = const("post gc mem")

async def garbage_collection_update():
    """
    See: https://docs.micropython.org/en/latest/reference/constrained.html#the-heap
    """
    gc.collect()
    gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
    print(CONST_MEM)
    print(mem_info())
