"""Web server."""

from collections.abc import Sequence
from http import HTTPStatus
from typing import Generic, TypeVar

from aiohttp.web import HTTPBadRequest, HTTPNotFound, Request, Response, RouteTableDef
from pydantic import BaseModel, TypeAdapter, ValidationError

from . import context
from .core import Player, PrivatePlayer

_T = TypeVar('_T')

api_routes = RouteTableDef()
_PlayerModel = TypeAdapter(Player)

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
async def _post_rooms(_: Request) -> Response:
    room = context.game.get().create_room()
    return model_response(room, status=HTTPStatus.CREATED, content_type=room.MEDIA_TYPE)

@api_routes.get('/rooms/{id}')
async def _get_room(request: Request) -> Response:
    try:
        room = context.game.get().rooms[request.match_info['id']]
    except KeyError as e:
        raise HTTPNotFound(text='{}', content_type='application/json') from e
    return model_response(room, content_type=room.MEDIA_TYPE)

@api_routes.get('/rooms/{id}/image.png')
async def _get_room_image(request: Request) -> Response:
    room = context.game.get().rooms[request.match_info['id']]
    body = await room.get_image()
    return Response(body=body, content_type='image/png')

@api_routes.get('/rooms/{id}/members')
async def _get_room_members(request: Request) -> Response:
    try:
        room = context.game.get().rooms[request.match_info['id']]
    except KeyError as e:
        raise HTTPNotFound(text='{}', content_type='application/json') from e
    return model_response(_Collection(items=room.with_members().members))

@api_routes.get('/members/{id}')
async def _get_member(request: Request) -> Response:
    try:
        member = context.game.get().members[request.match_info['id']]
    except KeyError as e:
        raise HTTPNotFound(text='{}', content_type='application/json') from e
    return model_response(member.with_player())
