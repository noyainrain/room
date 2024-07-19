"""Command-Line interface."""

import asyncio
from asyncio import CancelledError, Task, current_task, get_running_loop
from configparser import ConfigParser, ParsingError
from importlib import resources
import logging
from logging import getLogger
import signal
import sys
from threading import current_thread, main_thread
from typing import cast

from .game import Game
from .server import serve

async def main() -> int:
    """Run Room."""
    if current_thread() == main_thread():
        loop = get_running_loop()
        task = cast(Task[object], current_task())
        loop.add_signal_handler(signal.SIGINT, task.cancel) # type: ignore[misc]
        loop.add_signal_handler(signal.SIGTERM, task.cancel) # type: ignore[misc]

    logging.basicConfig(format='%(asctime)s %(levelname)s %(name)s: %(message)s',
                        level=logging.INFO)
    logger = getLogger(__name__)

    config = ConfigParser(strict=False, interpolation=None)
    with (resources.files(f'{__package__}.res') / 'default.ini').open() as f:
        config.read_file(f)
    try:
        config.read('room.ini')
    except ParsingError as e:
        logger.critical('Failed to load config file (%s)', e)
        return 1
    options = config['room']

    game = Game(data_path=options['data_path'])

    try:
        try:
            port = options.getint('port')
        except ValueError:
            logger.critical('Failed to load config file (Bad port type)')
            return 1
        try:
            server = await serve(game, host=options['host'], port=port, url=options['url'] or None)
        except OSError as e:
            logger.critical('Failed to start server (%s)', e)
            return 1
        logger.info('Started server at %s', server.url)

        try:
            try:
                game.create_data_directory()
            except FileExistsError:
                pass
            await game.run()
        except OSError as e:
            logger.critical('Failed to access data directory (%s)', e)
            return 1

        finally:
            await server.aclose()
            logger.info('Stopped server')

    except CancelledError:
        return 0

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
