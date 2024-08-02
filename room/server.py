"""Web server."""

from __future__ import annotations

from asyncio import create_task
from collections.abc import AsyncIterable, Awaitable, Callable, Sequence
from contextlib import AbstractContextManager
from datetime import timedelta
from http import HTTPStatus
from http.cookies import SimpleCookie
from importlib import resources
import logging
from logging import getLogger
from pathlib import Path
import re
from typing import Generic, TypeVar, Union, cast, get_type_hints
from urllib.parse import urlsplit, urlunsplit

from aiohttp import WSCloseCode
from aiohttp.abc import AbstractAccessLogger
from aiohttp.web import (
    Application, AppKey, AppRunner, BaseRequest, FileResponse, HTTPBadRequest, HTTPNotFound,
    HTTPUnauthorized, Request, Response, RouteTableDef, StaticResource, StreamResponse, TCPSite,
    WebSocketResponse, middleware)
from pydantic import BaseModel, TypeAdapter, ValidationError

from . import context
from .effects import Effect
from .core import Player, PrivatePlayer, Text
from .game import Action, FailedAction, FollowLinkEffect, Game, Member, OnlineRoom
from .util import WSMessage, cancel, template, timer

_T = TypeVar('_T')

_AnyAction = Union[OnlineRoom.UpdateRoomAction, OnlineRoom.PlaceTileAction, OnlineRoom.UseAction,
                   OnlineRoom.UpdateBlueprintAction, Member.MoveMemberAction]

_CLOSE_CODE_UNAUTHORIZED = 4001
_CLOSE_CODE_UNKNOWN_ROOM = 4004
_URL_KEY = AppKey('url', str)
_SECURE_KEY = AppKey('secure', bool)
_WEBSOCKETS_KEY = AppKey('websockets', set[WebSocketResponse])
_INDEX_HTML_KEY = AppKey('index_html', str)

api_routes = RouteTableDef()
ui_routes = RouteTableDef()
_PlayerModel = TypeAdapter(Player)
_ErrorModel = TypeAdapter(Text)
_AnyActionModel: TypeAdapter[_AnyAction] = TypeAdapter(_AnyAction)

def _escape_whitespace(text: str) -> str:
    return re.sub(r'\s', '·', text)

class _Collection(BaseModel, Generic[_T]): # type: ignore[misc]
    items: Sequence[_T]

class Error(BaseModel): # type: ignore[misc]
    """Error.

    .. attribute:: message

       Error message.
    """

    message: str

def model_response(model: BaseModel, *, status: int = 200,
                   content_type: str = 'application/json') -> Response:
    """Generate a JSON web response from a *model*."""
    return Response(text=model.model_dump_json(), status=status, content_type=content_type)

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

@api_routes.get('/players/self')
async def _get_current_player(_: Request) -> Response:
    return model_response(context.player.get())

@api_routes.put('/players/self')
async def _put_current_player(request: Request) -> Response:
    data = await request.text()
    try:
        patch = PrivatePlayer.model_validate_json(data)
    except ValidationError as e:
        raise HTTPBadRequest(text=Error(message=f'Bad request ({e})').model_dump_json(),
                             content_type='application/json') from e
    player = context.player.get()
    player.update(patch)
    return model_response(player)

@api_routes.get('/players/{id}')
async def _get_player(request: Request) -> Response:
    try:
        player = context.game.get().players[request.match_info['id']]
    except KeyError as e:
        raise HTTPNotFound(text='{}', content_type='application/json') from e
    return Response(body=_PlayerModel.dump_json(player), content_type='application/json')

@api_routes.post('/rooms')
async def _post_room(_: Request) -> Response:
    room = context.game.get().create_room()
    return model_response(room, status=HTTPStatus.CREATED, content_type=room.MEDIA_TYPE)

@api_routes.get('/rooms/{id}')
async def _get_room(request: Request) -> Response:
    try:
        room = context.game.get().get_room(request.match_info['id'])
    except KeyError as e:
        raise HTTPNotFound(text='{}', content_type='application/json') from e
    return model_response(room, content_type=room.MEDIA_TYPE)

@api_routes.get('/rooms/{id}/members')
async def _get_room_members(request: Request) -> Response:
    try:
        room = context.game.get().get_room(request.match_info['id'])
    except KeyError as e:
        raise HTTPNotFound(text='{}', content_type='application/json') from e
    return model_response(_Collection(items=room.with_members().members))

@api_routes.get('/rooms/{id}/actions')
async def _get_room_actions(request: Request) -> WebSocketResponse:
    logger = getLogger(__name__)
    websocket = WebSocketResponse()
    await websocket.prepare(request)
    websockets = request.app[_WEBSOCKETS_KEY]
    websockets.add(websocket)

    game = context.game.get()
    room_id = request.match_info['id']
    try:
        room = game.get_room(room_id)
    except KeyError:
        await websocket.close(code=_CLOSE_CODE_UNKNOWN_ROOM)
        return websocket
    context.room.set(room)

    async with room.enter() as member:
        async def write() -> None:
            async for action in member.actions():
                await websocket.send_str(action.model_dump_json())
        task = create_task(write())

        logger.info(
            '%s %s %s GET %s … (%d client(s) in %d room(s))', request.remote, member.player.id,
            _escape_whitespace(member.player.name), request.rel_url, len(websockets),
            game.get_overview().online_rooms)

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
                    logging.WARNING if error else logging.INFO, '%s %s %s %s %s %s %s (%.1fms)',
                    request.remote, member.player.id, _escape_whitespace(member.player.name),
                    action.type if action else 'Action', room.id, _escape_whitespace(room.title),
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

@api_routes.get('/members/{id}')
async def _get_member(request: Request) -> Response:
    try:
        member = context.game.get().members[request.match_info['id']]
    except KeyError as e:
        raise HTTPNotFound(text='{}', content_type='application/json') from e
    return model_response(member.with_player())

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
        secure = request.app[_SECURE_KEY]
        set_cookie(player.token, max_age=int(timedelta(days=365).total_seconds()), secure=secure,
                   httponly=True)
    else:
        set_cookie('', max_age=0)

@ui_routes.get('/')
@ui_routes.get('/invites/{id}')
async def _get_index(request: Request) -> Response:
    response = Response(text=request.app[_INDEX_HTML_KEY], content_type='text/html')
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
            logging.WARNING if response.status >= 400 else logging.INFO,
            '%s %s %s %s %s %d (%.1fms)', request.remote, player.id if player else '-',
            _escape_whitespace(player.name) if player else '-', request.method, request.rel_url,
            response.status, time * 1000)

class Server:
    """Game web server."""

    def __init__(self, _site: TCPSite, _runner: AppRunner, _websockets: set[WebSocketResponse],
                 _client_directory: AbstractContextManager[Path]) -> None:
        self._site = _site
        self._runner = _runner
        self._websockets = _websockets
        self._client_directory = _client_directory

    @property
    def url(self) -> str:
        """Public URL."""
        return self._runner.app[_URL_KEY]

    async def aclose(self) -> None:
        """Stop the server."""
        for websocket in set(self._websockets):
            await websocket.close(code=WSCloseCode.GOING_AWAY)
        await self._site.stop()
        await self._runner.cleanup()
        self._client_directory.__exit__(None, None, None)

async def serve(game: Game, *, host: str = '', port: int = 8080, url: str | None = None) -> Server:
    """Serve a *game* over the web.

    Incoming connections are listened for on *host* and *port*. *url* is the public URL.

    If there is a problem starting the server, an :exc:`OSError` is raised.
    """
    if url is None:
        url_host = host or 'localhost'
        url = f'http://{url_host}:{port}'

    client_directory = resources.as_file(resources.files(f'{__package__}.res') / 'client')
    client_path = client_directory.__enter__()

    try:
        websockets: set[WebSocketResponse] = set()

        api = Application(middlewares=[_authenticate])
        api.on_response_prepare.append(_update_cookie)
        api.add_routes(api_routes)
        api[_URL_KEY] = url
        api[_SECURE_KEY] = urlsplit(url).scheme == 'https'
        api[_WEBSOCKETS_KEY] = websockets

        app = Application()
        app.on_response_prepare.append(_configure_caching)
        app.add_routes(ui_routes)
        static = app.router.add_static('/static', client_path)
        assert isinstance(static, StaticResource)
        app.add_subapp('/api', api)
        app[_URL_KEY] = url
        t = template(f'{__package__}.res', 'client/index.html', double_braces=True)
        app[_INDEX_HTML_KEY] = t(shell=Shell(static), url=url)

        runner = AppRunner(app, access_log_class=_Logger)
        await runner.setup()

        try:
            site = TCPSite(runner, host, port)
            token = context.game.set(game)
            try:
                await site.start()
            finally:
                context.game.reset(token)

            return Server(site, runner, websockets, client_directory)

        except:
            await runner.cleanup()
            raise

    except:
        client_directory.__exit__(None, None, None)
        raise
