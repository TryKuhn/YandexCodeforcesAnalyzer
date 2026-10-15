"""Worker process: ``python -m authoring.worker``."""
import asyncio
import logging
import signal

from authoring.pipeline.runner import Worker


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover - Windows
            pass
    await Worker().run_forever(stop)


if __name__ == "__main__":
    asyncio.run(main())
