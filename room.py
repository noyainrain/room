"""TODO."""

from __future__ import annotations

import asyncio
from asyncio import CancelledError, Queue, create_task, sleep
import json
from pathlib import Path
import dataclasses
from dataclasses import dataclass
from collections.abc import AsyncGenerator
import logging
from logging import getLogger
import random
from string import ascii_lowercase
from typing import cast

from aiohttp import WSMsgType, WSCloseCode
from aiohttp.abc import AbstractAccessLogger
from aiohttp.client import ClientSession
from aiohttp.client_exceptions import ClientError, ClientPayloadError, ClientResponseError
from aiohttp.web import (BaseRequest, RouteTableDef, Request, Response, StreamResponse, TCPSite,
                         AppRunner, Application, WebSocketResponse)

game: Game = None
index_html = None
routes = RouteTableDef()

def randstr(length: int = 16, *, charset: str = ascii_lowercase) -> str:
    """Generate a random string.

    The string will have the given *length* and consist of characters from *charset*.
    """
    return ''.join(random.choice(charset) for _ in range(length))

class Tile:
    """TODO."""
    id: str
    image: str
    wall: bool

    def __init__(self, id: str, image: str, wall: bool) -> None:
        self.id = id
        self.image = image
        self.wall = wall

    @staticmethod
    def parse(data: dict[str, object]) -> Tile:
        return Tile(str(data['id']), str(data['image']), bool(data['wall']))

    def json(self) -> dict[str, object]:
        return {
            'id': self.id,
            'image': self.image,
            'wall': self.wall
        }

class Room:
    """TODO"""
    def __init__(self, id: str, blueprints: dict[str, Tile], tiles: list[Tiles]) -> None:
        self.id = id
        self.blueprints = blueprints
        self.tiles = tiles
        self._queues: set[Queue[Action]] = set()

    @staticmethod
    def parse(data: dict[str, object]) -> Room:
        blueprints_data = data['blueprints']
        assert isinstance(blueprints_data, dict)
        blueprints = {
            blueprint_id: Tile.parse(blueprint_data)
            for blueprint_id, blueprint_data in blueprints_data.items()
        }
        tiles_data = data['tile_ids']
        assert isinstance(tiles_data, list)
        tiles = [blueprints[tile_id] for tile_id in tiles_data]
        return Room(str(data['id']), blueprints, tiles)

    async def update_blueprint(self, action: UpdateBlueprintAction) -> None:
        """TODO."""
        # New blueprint
        if not action.blueprint.id:
            blueprint = Tile(randstr(), action.blueprint.image, action.blueprint.wall)
            action = dataclasses.replace(action, blueprint=blueprint)
        self.blueprints[action.blueprint.id] = action.blueprint
        await self.publish(action)

    async def use(self, action: UseAction) -> None:
        """TODO."""
        self.tiles[action.tile_index] = self.blueprints[action.item_id]
        await self.publish(action)

    async def move(self, action: MoveAction) -> None:
        """TODO."""
        await self.publish(action)

    async def actions(self) -> AsyncGenerator[Action, None]:
        """TODO."""
        queue: Queue[Action] = Queue()
        self._queues.add(queue)
        user_id = randstr()
        yield JoinAction(user_id=user_id, room=self)
        while True:
            try:
                yield await queue.get()
            except CancelledError:
                self._queues.remove(queue)
                await self.publish(MoveAction(user_id, (-1, -1)))
                raise
            # TODO handle
            #except GeneratorExit:
            #    break
        print('EXIT ACITONS')

    async def publish(self, action: Action) -> None:
        # print('PUBLISH', message)
        for queue in self._queues:
            await queue.put(action)

    def json(self) -> dict[str, object]:
        """TODO."""
        return {
            'id': self.id,
            'blueprints': {
                blueprint_id: blueprint.json()
                for blueprint_id, blueprint in self.blueprints.items()
            },
            'tile_ids': [tile.id for tile in self.tiles]
        }

@dataclass
class Action:
    """TODO."""
    user_id: str

    def json(self) -> dict[str, object]:
        return {'type': type(self).__name__, 'user_id': self.user_id}

@dataclass
class JoinAction(Action):
    """TODO."""
    room: Room

    def json(self) -> dict[str, object]:
        return {**super().json(), 'room': self.room.json()}

@dataclass
class UpdateBlueprintAction(Action):
    """TODO."""
    blueprint: Tile

    @staticmethod
    def parse(data: dict[str, object]) -> UpdateBlueprintAction:
        return UpdateBlueprintAction(str(data['user_id']), Tile.parse(data['blueprint']))

    def json(self) -> dict[str, object]:
        return {**super().json(), 'blueprint': self.blueprint.json()}

@dataclass
class UseAction(Action):
    """TODO."""
    tile_index: int
    item_id: str

    @staticmethod
    def parse(data: dict[str, object]) -> UseAction:
        return UseAction(str(data['user_id']), int(data['tile_index']), str(data['item_id']))

    def json(self) -> dict[str, object]:
        return {**super().json(), 'tile_index': self.tile_index, 'item_id': self.item_id}

@dataclass
class MoveAction(Action):
    """TODO."""
    position: tuple[float, float]

    @staticmethod
    def parse(data: dict[str, object]) -> MoveAction:
        return MoveAction(str(data['user_id']), tuple(data['position']))

    def json(self) -> dict[str, object]:
        return {**super().json(), 'position': self.position}

IMAGES = {
    'void': (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAKElEQVQYV2NkYGD4D8Q4ASNIQWhoKMPq1atRFMHEwAoImkAHBRQ5EgCbrhQB2kRr+QAAAABJRU5ErkJggg==',
        False
    ),
    'grass': (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAOElEQVQYV2NkWMXwnwEPYAQpCA0NZVi9ejVWZRgK0BWDFSBrJagA3R64Ceg6YXycCmAmYbgB3QoAnmIiUcgpwTgAAAAASUVORK5CYII=',
        False
    ),
    'floor': (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFElEQVQYV2NctWrVfwY8gHFkKAAApMMX8a16WAwAAAAASUVORK5CYII=',
        False
    ),
    'wall-h-left': (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAANUlEQVQYV2MMDQ39z4AHMIIUhDKsxqkErIBoE1YzhALhaiCE0CCAYgVBBTCrcJqAzS0EHQkARNYe+TqxIDUAAAAASUVORK5CYII=',
        True
    ),
    'wall-h-middle': (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAALElEQVQYV2MMDQ39z4AHMK4KZcCvgGgTVjOEAuFqIITQMAC3gmgF6O6l3JEA6qkZ+Y/de7cAAAAASUVORK5CYII=',
        True
    ),
    'wall-h-right': (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAMklEQVQYV2MMDQ39z4AHMK4KZcCpYDVDKAMjSSaAdIQyrAZCBI1iBdEKYG4Gu4FiRwIA43Ue+WpSWc4AAAAASUVORK5CYII=',
        True
    ),
    'wall-v-middle': (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAG0lEQVQYV2MMDQ39H8qwmgEbWM0QysA4MhQAAD2TH/nrMiedAAAAAElFTkSuQmCC',
        True
    ),
    'wall-corner-bl': (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAANklEQVQYV2MMDQ39H8qwmgEbWM0QysCITwFIE1gBVu1QQQwTQMaCrITRpCuAWYfTBHT3EHQkAAj0IPmuXnNhAAAAAElFTkSuQmCC',
        True
    ),
    'wall-corner-br': (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAPElEQVQYV2MMDQ39H8qwmgEbWM0QysC4KpThP1ZZoCBYAcgEXApA4mATQCpB1sBomAa4FUQrQLeKOo4EAB+iIPk9A4o5AAAAAElFTkSuQmCC',
        True
    ),
    'wall-corner-tl': (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAIUlEQVQYV2MMDQ39z4AHMIIUhDKsxqkEr4LVDKEMQ0IBAIgQHPlqSMNBAAAAAElFTkSuQmCC',
        True
    ),
    'wall-corner-tr': (
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAJUlEQVQYV2MMDQ39z4AHMK4KZcCpYDVDKAMjyIRQhtVYzRgyCgBxZhz5QKrMXgAAAABJRU5ErkJggg==',
        True
    )
}

class Game:
    """TODO."""

    def __init__(self) -> None:
        """TODO."""
        self.rooms: dict[str, Room] = {}

    def create_room(self) -> Room:
        """TODO."""
        blueprints = {
            tile.id: tile
            for tile in (Tile(randstr(), image, wall) for image, wall in IMAGES.values())
        }
        void = next(iter(blueprints.values()))
        #void = Tile(id=randstr(), image=VOID_IMAGE, wall=False)
        tiles = [void] * (8 * 8)
        room = Room(id=randstr(), blueprints=blueprints, tiles=tiles)
        self.rooms[room.id] = room
        return room

    async def run(self) -> None:
        for path in Path('data').iterdir():
            data = json.loads(path.read_text(encoding='utf-8'))
            room = Room.parse(data)
            self.rooms[room.id] = room

        while True:
            # await sleep(5 * 60)
            await sleep(5)
            for room in self.rooms.values():
                path = Path('data', f'{room.id}.json')
                path.write_text(json.dumps(room.json()), encoding='utf-8')
                getLogger(__name__).info(f'Stored {path}')

@routes.get('/rooms/{id}')
async def _rooms(request: Request) -> WebSocketResponse:
    websocket = WebSocketResponse()
    await websocket.prepare(request)

    room_id = request.match_info['id']
    if room_id == 'new':
        room = game.create_room()
    else:
        room = game.rooms[room_id]

    async def write() -> None:
        actions = room.actions()
        print('STARTED WRITE LOOP')
        try:
            async for action in actions:
                #print('SENDING MESSAGE', action)
                # await websocket.send_str(json.dumps(action.json()))
                    await websocket.send_json(action.json())
        except CancelledError:
            print('CANCELLED')
        finally:
            print('CLOSED WRITE LOOP')
            await actions.aclose()
            await actions.aclose()
            print('AFTER ACLOSE')
    task = create_task(write())

    getLogger(__name__).info('Client joined (%s)', request.remote)

    async for message in websocket:
        print('WEBSOCKET MESSAGE', message.data)
        # data = cast(dict[str, object], json.loads(message))
        data = cast(dict[str, object], message.json())
        if data['type'] == 'UpdateBlueprintAction':
            await room.update_blueprint(UpdateBlueprintAction.parse(data))
        elif data['type'] == 'UseAction':
            await room.use(UseAction.parse(data))
        elif data['type'] == 'MoveAction':
            await room.move(MoveAction.parse(data))
        else:
            assert False
        #try:
        #except Exception:
        #    getLogger(__name__).exception('FATAL')

    task.cancel()

    return websocket

@routes.get('/')
async def _index(_: Request) -> Response:
    return Response(text=index_html, content_type='text/html')

routes.static('/static', 'www', follow_symlinks=True)

async def main() -> None:
    """TODO."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    logger = getLogger(__name__)

    global game, index_html
    game = Game()

    index_html = Path('index.html').read_text(encoding='utf-8')

    runner = None
    site = None
    app = Application()
    #app['community'] = community
    app.add_routes(routes)
    # runner = AppRunner(app, access_log_class=Logger)
    runner = AppRunner(app)
    await runner.setup()
    site = TCPSite(runner, 'localhost', 8000)
    await site.start()
    logger.info('Started server')

    try:
        await game.run()
    finally:
        await site.stop()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
