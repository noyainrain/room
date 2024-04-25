"""TODO."""

from collections.abc import Sequence
from http import HTTPStatus

from aiohttp.web import Request, Response, RouteTableDef
from aiohttp.web import HTTPNotFound
from pydantic import TypeAdapter

from . import context
from .core import Player
from .game import MemberWithPlayer

api_routes = RouteTableDef()

_PlayerModel = TypeAdapter(Player)
_MembersModel: TypeAdapter[Sequence[MemberWithPlayer]] = TypeAdapter(Sequence[MemberWithPlayer])

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
    return Response(status=HTTPStatus.CREATED, text=room.model_dump_json(),
                    content_type='application/json')

@api_routes.get('/rooms/{id}')
async def _get_room(request: Request) -> Response:
    try:
        room = context.game.get().rooms[request.match_info['id']]
    except KeyError as e:
        raise HTTPNotFound(text='{}', content_type='application/json') from e
    return Response(text=room.model_dump_json(), content_type='application/json')

@api_routes.get('/rooms/{id}/members')
async def _get_room_members(request: Request) -> Response:
    try:
        room = context.game.get().rooms[request.match_info['id']]
    except KeyError as e:
        raise HTTPNotFound(text='{}', content_type='application/json') from e
    return Response(body=_MembersModel.dump_json(room.with_members().members),
                    content_type='application/json')

@api_routes.get('/members/{id}')
async def _get_member(request: Request) -> Response:
    try:
        member = context.game.get().members[request.match_info['id']]
    except KeyError as e:
        raise HTTPNotFound(text='{}', content_type='application/json') from e
    return Response(text=member.with_player().model_dump_json(), content_type='application/json')
