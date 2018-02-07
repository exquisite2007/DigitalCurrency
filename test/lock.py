import asyncio
import functools


def unlock(lock):
    print('callback releasing lock')
    lock.release()


async def coro1(lock):
    # lock.locked()
    print('coro1 waiting for the lock')
    await lock
    try:
        await asyncio.sleep(3)
        print('coro1 acquired lock')
    finally:
        print('coro1 released lock')
        lock.release()


async def coro2(lock):
    # lock.locked()
    print('coro2 waiting for the lock')
    await lock
    try:
        await asyncio.sleep(3)
        print('coro2 acquired lock')
    finally:
        print('coro2 released lock')
        lock.release()
async def coro3(lock):
    # lock.locked()
    print('coro3 waiting for the lock')
    await lock
    try:
        await asyncio.sleep(3)
        print('coro3 acquired lock')
    finally:
        print('coro3 released lock')
        lock.release()

async def main(loop):
    # Create and acquire a shared lock.
    lock = asyncio.Lock()
    print('acquiring the lock before starting coroutines')
    # await lock.acquire()
    # print('lock acquired: {}'.format(lock.locked()))

    # # Schedule a callback to unlock the lock.
    # loop.call_later(10, functools.partial(unlock, lock))

    # Run the coroutines that want to use the lock.
    print('waiting for coroutines')
    await asyncio.wait([coro2(lock),coro1(lock),coro3(lock)]),


event_loop = asyncio.get_event_loop()
try:
    event_loop.run_until_complete(main(event_loop))
finally:
    event_loop.close()