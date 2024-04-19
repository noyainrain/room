"""TODO."""

from aiohttp.web import Request, Response, RouteTableDef
from aiohttp.web import HTTPNotFound
from http import HTTPStatus
from pydantic import TypeAdapter

from . import context
from .game import OnlineRoom

api_routes = RouteTableDef()

# OQ why does aiohttp handle /api/rooms/ and /api/rooms/x differently

@api_routes.post('/rooms')
async def _post_rooms(_: Request) -> Response:
    room = context.game.get().create_room()
    return Response(status=HTTPStatus.CREATED, body=TypeAdapter(OnlineRoom).dump_json(room),
                    content_type='application/json')

@api_routes.get('/rooms/{id}')
async def _get_room(request: Request) -> Response:
    print('GET ROOM', request.match_info['id'])
    try:
        # OQ add game.get_room(id)?
        room = context.game.get().rooms[request.match_info['id']]
    except KeyError as e:
        # OQ API error code?
        raise HTTPNotFound() from e
    # OQ does TypeAdapter have some caching?
    return Response(body=TypeAdapter(OnlineRoom).dump_json(room), content_type='application/json')
