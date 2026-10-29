"""Serve the public lab and private legacy API in one shared Python process.

Sharing provider imports avoids loading Pipecat twice on the free instance.
Only the lab port is public. The supervisor owns process signals.
"""
import asyncio
from contextlib import contextmanager
import os
import signal
import uvicorn


class SupervisedServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self):
        yield

    def install_signal_handlers(self):
        pass


async def main():
    servers = [
        SupervisedServer(uvicorn.Config("backend.main:app", host="127.0.0.1", port=8000)),
        SupervisedServer(uvicorn.Config("backend.lab_server:app", host="0.0.0.0",
                         port=int(os.getenv("PORT", "10000")), ws_max_size=1500000)),
    ]
    def stop(*_args):
        for server in servers:
            server.should_exit = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    tasks = [asyncio.create_task(server.serve()) for server in servers]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        stop()
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
