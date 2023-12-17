"""Command-Line interface."""

import asyncio
from asyncio import CancelledError, Task, create_task, current_task, get_running_loop
from collections.abc import AsyncIterable
from configparser import ConfigParser, ParsingError
from http import HTTPStatus
from importlib import resources
import logging
from logging import getLogger
import signal
import sys
from threading import current_thread, main_thread
from typing import Annotated, Union, cast

from aiohttp import WSCloseCode
from aiohttp.abc import AbstractAccessLogger
from aiohttp.web import (Application, AppRunner, BaseRequest, HTTPBadRequest, Request, Response,
                         RouteTableDef, StreamResponse, TCPSite, WebSocketResponse)
from pydantic import StringConstraints, TypeAdapter, ValidationError

from . import context
from .game import FailedAction, Game, OnlineRoom, Player
from .util import WSMessage, cancel, timer

_NonblankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_AnyAction = Union[OnlineRoom.PlaceTileAction, OnlineRoom.UseAction,
                   OnlineRoom.UpdateBlueprintAction, Player.MovePlayerAction]

_CLOSE_CODE_UNKNOWN_ROOM = 4004

routes = RouteTableDef()
_ErrorModel = TypeAdapter(_NonblankStr)
_AnyActionModel = TypeAdapter(_AnyAction)

@routes.get('/rooms')
@routes.get('/rooms/{id}')
async def _rooms(request: Request) -> WebSocketResponse:
    logger = getLogger(__name__)
    websocket = WebSocketResponse()
    await websocket.prepare(request)
    websockets = cast(set[WebSocketResponse], request.app['websockets'])
    websockets.add(websocket)

    game = context.game.get()
    room_id = request.match_info.get('id')
    if not room_id:
        room = game.create_room()
    else:
        try:
            room = game.rooms[room_id]
        except KeyError:
            await websocket.close(code=_CLOSE_CODE_UNKNOWN_ROOM)
            return websocket
    context.room.set(room)

    async with room.join() as player:
        async def write() -> None:
            async for action in player.actions():
                await websocket.send_str(action.model_dump_json())
        task = create_task(write())

        request['player'] = player
        room_players = [count for room in game.rooms.values() if (count := len(room.players))]
        logger.info('%s %s GET %s … (%d client(s) in %d room(s))', request.remote, player.id,
                    request.rel_url, sum(room_players), len(room_players))

        async for message in cast(AsyncIterable[WSMessage], websocket):
            with timer() as t:
                # pylint: disable=broad-exception-caught
                action = None
                error = None
                try:
                    assert isinstance(message.data, str)
                    action = cast(_AnyAction,
                                  _AnyActionModel.validate_json(message.data, strict=True))
                    if action.player_id != player.id:
                        raise ValueError('Forbidden action')
                    await action.perform()
                except ValidationError as e:
                    error = f'Bad message ({e})'
                except ValueError as e:
                    error = str(e)
                except IndexError:
                    error = 'Unknown index'
                except LookupError as e:
                    error = f"Unknown key {e.args[0]}" # type: ignore[misc]
                except Exception:
                    logger.exception('Unhandled error')
                    error = 'Unhandled server error'
                if error:
                    await websocket.send_str(
                        FailedAction(player_id=player.id, message=error).model_dump_json())
            if not isinstance(action, Player.MovePlayerAction):
                logger.log(
                    logging.WARNING if error else logging.INFO, '%s %s %s @%s %s (%.1fms)',
                    request.remote, player.id, action.type if action else 'Action', room.id,
                    'error' if error else 'ok', t() * 1000)
        await cancel(task)

    websockets.remove(websocket)
    return websocket

@routes.get('/')
async def _get_index(request: Request) -> Response:
    return Response(text=cast(str, request.app['index_html']), content_type='text/html')

@routes.post('/errors')
async def _post_errors(request: Request) -> Response:
    try:
        getLogger(__name__).error('Unhandled client error\n%s',
                                  _ErrorModel.validate_python(await request.read()))
    except ValidationError as e:
        raise HTTPBadRequest(text=f'Bad request ({e})', content_type='text/plain') from None
    return Response(status=HTTPStatus.NO_CONTENT)

class _Logger(AbstractAccessLogger):
    def log(self, request: BaseRequest, response: StreamResponse, time: float) -> None:
        player = cast('Player | None', request.get('player'))
        getLogger(__name__).log(
            logging.WARNING if response.status >= 400 else logging.INFO, '%s %s %s %s %d (%.1fms)',
            request.remote, player.id if player else '-', request.method, request.rel_url,
            response.status, time * 1000)

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

    res = resources.files(f'{__package__}.res')
    config = ConfigParser(strict=False, interpolation=None)
    with (res / 'default.ini').open() as f:
        config.read_file(f)
    try:
        config.read('room.ini')
    except ParsingError as e:
        logger.critical('Failed to load config file (%s)', e)
        return 1
    options = config['room']

    game = Game(data_path=options['data_path'])
    context.game.set(game)

    try:
        with resources.as_file(res / 'client') as client_path:
            host = options['host']
            try:
                port = options.getint('port')
            except ValueError:
                logger.critical('Failed to load config file (Bad port type)')
                return 1
            url_host = host or 'localhost'
            url = options['url'] or f'http://{url_host}:{port}'

            app = Application()
            app.add_routes(routes)
            app.router.add_static('/static', client_path)
            websockets: set[WebSocketResponse] = set()
            app['websockets'] = websockets
            app['index_html'] = (client_path / 'index.html').read_text().replace('{url}', url)

            runner = None
            site = None
            try:
                runner = AppRunner(app, access_log_class=_Logger)
                await runner.setup()
                site = TCPSite(runner, host, port)
                try:
                    await site.start()
                except OSError as e:
                    logger.critical('Failed to start server (%s)', e)
                    return 1
                logger.info('Started server at %s', url)

                try:
                    game.data_path.mkdir(exist_ok=True)
                    await game.run()
                except OSError as e:
                    logger.critical('Failed to access data directory (%s)', e)
                    return 1

            finally:
                for websocket in set(websockets):
                    await websocket.close(code=WSCloseCode.GOING_AWAY)
                if site:
                    await site.stop()
                    logger.info('Stopped server')
                if runner:
                    await runner.cleanup()

    except CancelledError:
        return 0

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
