"""Command-Line interface."""

import asyncio
from asyncio import CancelledError, Task, create_task, current_task, get_running_loop
from collections.abc import AsyncIterable, Awaitable, Callable
from configparser import ConfigParser, ParsingError
from datetime import timedelta
from http import HTTPStatus
from http.cookies import SimpleCookie
from importlib import resources
import logging
from logging import getLogger
import signal
import sys
from threading import current_thread, main_thread
from typing import Union, cast, get_type_hints
from urllib.parse import urlsplit, urlunsplit

from aiohttp import WSCloseCode
from aiohttp.abc import AbstractAccessLogger
from aiohttp.web import (
    Application, AppKey, AppRunner, BaseRequest, FileResponse, HTTPBadRequest, HTTPUnauthorized,
    Request, Response, RouteTableDef, StaticResource, StreamResponse, TCPSite, WebSocketResponse,
    middleware)
from pydantic import TypeAdapter, ValidationError

from . import context
from .core import Text
from .game import Action, Effect, FailedAction, FollowLinkEffect, Game, Member, OnlineRoom
from .server import api_routes
from .util import WSMessage, cancel, template, timer

_AnyAction = Union[OnlineRoom.UpdateRoomAction, OnlineRoom.PlaceTileAction, OnlineRoom.UseAction,
                   OnlineRoom.UpdateBlueprintAction, Member.MoveMemberAction]

_URL_KEY = AppKey("url", str)
_CLOSE_CODE_UNAUTHORIZED = 4001
_CLOSE_CODE_UNKNOWN_ROOM = 4004

ui_routes = RouteTableDef()

_ErrorModel = TypeAdapter(Text)
_AnyActionModel: TypeAdapter[_AnyAction] = TypeAdapter(_AnyAction)

class Shell:
    """Files comprising the application shell.

    .. attribute:: static

       Web resource serving the directory of static files.
    """

    def __init__(self, static: StaticResource) -> None:
        self.static = static

    def url(self, path: str) -> str:
        """Generate a versioned URL for the file at *path*."""
        return str(self.static.url_for(filename=path, append_version=True))

@api_routes.get('/rooms/{id}/actions')
async def _rooms(request: Request) -> WebSocketResponse:
    logger = getLogger(__name__)
    websocket = WebSocketResponse()
    await websocket.prepare(request)
    websockets = cast(set[WebSocketResponse], request.app['websockets'])
    websockets.add(websocket)

    game = context.game.get()
    room_id = request.match_info['id']
    try:
        room = game.rooms[room_id]
    except KeyError:
        await websocket.close(code=_CLOSE_CODE_UNKNOWN_ROOM)
        return websocket
    context.room.set(room)

    async with room.enter() as member:
        async def write() -> None:
            async for action in member.actions():
                await websocket.send_str(action.model_dump_json())
        task = create_task(write())

        room_members = [count for room in game.rooms.values() if (count := len(room.members))]
        logger.info('%s %s GET %s … (%d client(s) in %d room(s))', request.remote, member.player.id,
                    request.rel_url, sum(room_members), len(room_members))

        async for message in cast(AsyncIterable[WSMessage], websocket):
            with timer() as t:
                # pylint: disable=broad-exception-caught
                action = None
                error = None
                try:
                    assert isinstance(message.data, str)
                    action = cast(_AnyAction,
                                  _AnyActionModel.validate_json(message.data, strict=True))
                    if action.member_id != member.id:
                        raise ValueError('Forbidden action')
                    perform = _actions.get(type(action)) or _perform
                    await perform(action, request.app)
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
                        FailedAction(member_id=member.id, message=error).model_dump_json())
            if not isinstance(action, Member.MoveMemberAction):
                logger.log(
                    logging.WARNING if error else logging.INFO, '%s %s %s @%s %s (%.1fms)',
                    request.remote, member.player.id, action.type if action else 'Action', room.id,
                    'error' if error else 'ok', t() * 1000)
        await cancel(task)

    websockets.remove(websocket)
    return websocket

async def _update_blueprint(action: Action, api: Application) -> None:
    def rewrite_effect_url(effect: Effect) -> Effect:
        if isinstance(effect, FollowLinkEffect):
            components = urlsplit(effect.url)
            origin = f'{components.scheme}://{components.netloc}'
            if origin == api[_URL_KEY]:
                url = urlunsplit(('', '', components.path, components.query, components.fragment))
                effect = effect.model_copy(update={'url': url}) # type: ignore[misc]
        return effect

    assert isinstance(action, OnlineRoom.UpdateBlueprintAction)
    effects = {
        cause:
            [rewrite_effect_url(effect) for effect in effects]
            for cause, effects in action.blueprint.effects.items()
    }
    blueprint = action.blueprint.model_copy(update={'effects': effects}) # type: ignore[misc]
    action = action.model_copy(update={'blueprint': blueprint}) # type: ignore[misc]
    await action.perform()

async def _perform(action: Action, _: Application) -> None:
    await action.perform()

_actions: dict[type[Action], Callable[[Action, Application], Awaitable[None]]] = {
    OnlineRoom.UpdateBlueprintAction: _update_blueprint
}

@middleware
async def _authenticate(request: Request,
                        handler: Callable[[Request], Awaitable[StreamResponse]]) -> StreamResponse:
    game = context.game.get()
    if token := request.cookies.get('token'):
        try:
            player = game.authenticate(token)
        except LookupError as e:
            response_type = (
                get_type_hints(request.match_info.handler)['return']) # type: ignore[misc]
            if (
                isinstance(response_type, type) # type: ignore[misc]
                and issubclass(response_type, WebSocketResponse)
            ):
                websocket = WebSocketResponse()
                await websocket.prepare(request)
                await websocket.close(code=_CLOSE_CODE_UNAUTHORIZED)
                return websocket
            raise HTTPUnauthorized() from e
    else:
        player = game.sign_in()
    context.player.set(player)

    return await handler(request)

async def _update_cookie(request: Request, response: StreamResponse) -> None:
    # StreamResponse.set_cookie() only works before headers have been prepared
    def set_cookie(value: str, *, max_age: 'int | None' = None, secure: bool = False,
                   httponly: bool = False) -> None:
        cookies = SimpleCookie()
        cookies['token'] = value
        cookie = cookies['token']
        cookie['path'] = '/'
        if max_age is not None:
            cookie['max-age'] = max_age
        cookie['secure'] = secure
        cookie['httponly'] = httponly
        response.headers.add('Set-Cookie', cookie.output(header='')[1:])

    if player := context.player.get(None):
        secure = request.app['secure'] # type: ignore[misc]
        assert isinstance(secure, bool) # type: ignore[misc]
        set_cookie(player.token, max_age=int(timedelta(days=365).total_seconds()), secure=secure,
                   httponly=True)
    else:
        set_cookie('', max_age=0)

@ui_routes.get('/')
@ui_routes.get('/invites/{id}')
async def _get_index(request: Request) -> Response:
    response = Response(text=cast(str, request.app['index_html']), content_type='text/html')
    response.enable_compression()
    return response

@ui_routes.post('/errors')
async def _post_errors(request: Request) -> Response:
    try:
        getLogger(__name__).error('Unhandled client error\n%s',
                                  _ErrorModel.validate_python(await request.read()))
    except ValidationError as e:
        raise HTTPBadRequest(text=f'Bad request ({e})', content_type='text/plain') from None
    return Response(status=HTTPStatus.NO_CONTENT)

async def _configure_caching(_: Request, response: StreamResponse) -> None:
    # See https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching#common_caching_patterns
    response.headers['Cache-Control'] = ('public, max-age=31536000'
                                         if isinstance(response, FileResponse) else 'no-cache')

class _Logger(AbstractAccessLogger):
    def log(self, request: BaseRequest, response: StreamResponse, time: float) -> None:
        player = context.player.get(None)
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

            api = Application(middlewares=[_authenticate])
            api.on_response_prepare.append(_update_cookie)
            api.add_routes(api_routes)
            api[_URL_KEY] = url
            api['secure'] = urlsplit(url).scheme == 'https'
            websockets: set[WebSocketResponse] = set()
            api['websockets'] = websockets

            app = Application()
            app.on_response_prepare.append(_configure_caching)
            app.add_routes(ui_routes)
            static = app.router.add_static('/static', client_path)
            assert isinstance(static, StaticResource)
            app.add_subapp('/api', api)
            t = template(f'{__package__}.res', 'client/index.html', double_braces=True)
            app['index_html'] = t(shell=Shell(static), url=url)

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
                    try:
                        game.create_data_directory()
                    except FileExistsError:
                        pass
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
