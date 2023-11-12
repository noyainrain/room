"""Game logic.

.. data:: DEFAULT_BLUEPRINTS

   Default tile blueprints by ID.
"""

from __future__ import annotations

from asyncio import Queue, sleep
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from logging import getLogger
from os import PathLike
from pathlib import Path
from typing import ClassVar, Literal, NoReturn, TypeVar

from pydantic import (BaseModel, Field, PrivateAttr, TypeAdapter, computed_field, field_validator,
                      model_validator)

from . import context
from .util import open_image_data_url, randstr, timer

A = TypeVar('A', bound='Action')

class Action(BaseModel): # type: ignore[misc]
    """Player action.

    .. attribute:: player_id

       ID of the player performing the action.
    """
    player_id: str

    @computed_field # type: ignore[misc]
    @property
    def type(self) -> str:
        """Type of the action."""
        return type(self).__name__

    @property
    def player(self) -> Player:
        """Player performing the action."""
        try:
            return context.room.get().players[self.player_id]
        except KeyError:
            raise ReferenceError(self.player_id) from None

    async def perform(self: A) -> A:
        """Perform the action.

        An action with result information is returned.

        May be overriden by subclass. By default, self is returned.
        """
        return self

class FailedAction(Action): # type: ignore[misc]
    """Failed action.

    .. attribute:: message

       Error message.
    """

    message: str

class Player(BaseModel): # type: ignore[misc]
    """Present player.

    .. attribute:: id

       Unique player ID.

    .. attribute:: position

       Current position in px.
    """

    id: str
    position: tuple[float, float]
    _queue: Queue[Action] = PrivateAttr(default_factory=Queue)

    async def actions(self) -> AsyncGenerator[Action, None]:
        """Stream of actions intended for the player."""
        while True:
            yield await self._queue.get()

    async def publish(self, action: Action) -> None:
        """Publish an *action* to the player."""
        await self._queue.put(action)

    class MovePlayerAction(Action): # type: ignore[misc]
        """Action of moving the player.

        .. attribute:: position

           Target position.
        """

        position: tuple[float, float]

        async def perform(self) -> Player.MovePlayerAction:
            room = context.room.get()
            size = room.SIZE * Tile.SIZE
            if not (0 <= self.position[0] < size and 0 <= self.position[1] < size):
                raise ValueError(f'Out-of-range position {self.position}')
            self.player.position = self.position
            await room.publish(self)
            return self

class Tile(BaseModel): # type: ignore[misc]
    """Room tile.

    .. attribute:: id

       Unique tile ID.

    .. attribute:: image

       Image as data URL.

    .. attribute:: wall

       Indicates if the tile is impassable.

    .. attribute:: SIZE

       Tile width and height in px.
    """

    SIZE: ClassVar[int] = 8

    id: str
    image: str
    wall: bool

    @field_validator('image')
    @classmethod
    def _check_image(cls, image: str) -> str:
        with open_image_data_url(image) as obj:
            if not obj.width == obj.height == cls.SIZE:
                raise ValueError(f'Bad image size {obj.width} x {obj.height} px')
        return image

class OfflineRoom(BaseModel): # type: ignore[misc]
    """Room file.

    .. attribute:: id

       Unique room ID.

    .. attribute:: tile_ids

       Grid of room tiles, referenced by ID, serialized in row direction.

    .. attribute:: blueprints

       Tile blueprints by ID.

    .. attribute:: version

       Room file version.

    .. attribute:: SIZE

       Room width and height.
    """

    SIZE: ClassVar[int] = 8

    id: str
    tile_ids: list[str]
    blueprints: dict[str, Tile]
    version: Literal['0.1']

    @model_validator(mode='before')
    @classmethod
    def _check(cls, data: dict[str, object]) -> dict[str, object]:
        # Update to version 0.1
        if 'version' not in data:
            data['version'] = '0.1'
        return data

    @property
    def tiles(self) -> list[Tile]:
        """Grid of room tiles, serialized in row direction."""
        return [self.blueprints[tile_id] for tile_id in self.tile_ids]

_OfflineRoomModel = TypeAdapter(OfflineRoom)

class OnlineRoom(OfflineRoom): # type: ignore[misc]
    """Creative space.

    .. attribute:: players

       Present players by ID.
    """

    players: dict[str, Player] = Field(default_factory=dict)

    @asynccontextmanager
    async def join(self) -> AsyncGenerator[Player, None]:
        """Context manager to create a player and join the room.

        On exit, leave the room again.
        """
        player = Player(id=randstr(), position=(self.SIZE * Tile.SIZE / 2, ) * 2)
        await self.publish(Player.MovePlayerAction(player_id=player.id, position=player.position))
        self.players[player.id] = player
        await player.publish(self.WelcomeAction(player_id=player.id, room=self))
        yield player

        del self.players[player.id]
        await self.publish(Player.MovePlayerAction(player_id=player.id, position=(-1, -1)))

    async def publish(self, action: Action) -> None:
        """Publish an *action* to all players."""
        for player in self.players.values():
            await player.publish(action)

    class WelcomeAction(Action): # type: ignore[misc]
        """Handshake action.

        .. attribute:: room

           Joined room.
        """

        room: OnlineRoom

    class UseAction(Action): # type: ignore[misc]
        """Action of using a tile.

        .. attribute:: tile_index

           Index of the used tile.

        .. attribute:: item_id

           ID of the used item.
        """

        tile_index: int
        item_id: str

        async def perform(self) -> OnlineRoom.UseAction:
            room = context.room.get()
            if not 0 <= self.tile_index < room.SIZE * room.SIZE:
                raise ValueError(f'Out-of-range tile_index {self.tile_index}')
            if self.item_id not in room.blueprints:
                raise ValueError(f'No blueprints item {self.item_id}')
            room.tile_ids[self.tile_index] = self.item_id
            await room.publish(self)
            return self

    class UpdateBlueprintAction(Action): # type: ignore[misc]
        """Action of updating a tile blueprint.

        If :attr:`blueprint` *id* is empty, a new blueprint is created.

        .. attribute:: blueprint

           Updated tile blueprint.
        """

        blueprint: Tile

        async def perform(self) -> OnlineRoom.UpdateBlueprintAction:
            room = context.room.get()
            if self.blueprint.id:
                if self.blueprint.id not in room.blueprints:
                    raise ValueError(f'No blueprints item {self.blueprint.id}')
                action = self
            else:
                blueprint = self.blueprint.model_copy(update={'id': randstr()}) # type: ignore[misc]
                action = self.model_copy(update={'blueprint': blueprint}) # type: ignore[misc]

            room.blueprints[action.blueprint.id] = action.blueprint
            await room.publish(action)
            return action

DEFAULT_BLUEPRINTS = {
    'void': Tile(
        id='',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAKElEQVQYV2NkYGD4'
            'D8Q4ASNIQWhoKMPq1atRFMHEwAoImkAHBRQ5EgCbrhQB2kRr+QAAAABJRU5ErkJggg==',
        wall=False),
    'grass': Tile(
        id='',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAOElEQVQYV2NkWMXw'
            'nwEPYAQpCA0NZVi9ejVWZRgK0BWDFSBrJagA3R64Ceg6YXycCmAmYbgB3QoAnmIiUcgpwTgAAAAASUVORK5CYI'
            'I=',
        wall=False
    ),
    'floor': Tile(
        id='',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFElEQVQYV2NctWrV'
            'fwY8gHFkKAAApMMX8a16WAwAAAAASUVORK5CYII=',
        wall=False
    ),
    'wall-left': Tile(
        id='',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAANUlEQVQYV2MMDQ39'
            'z4AHMIIUhDKsxqkErIBoE1YzhALhaiCE0CCAYgVBBTCrcJqAzS0EHQkARNYe+TqxIDUAAAAASUVORK5CYII=',
        wall=True
    ),
    'wall-horizontal': Tile(
        id='',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAALElEQVQYV2MMDQ39'
            'z4AHMK4KZcCvgGgTVjOEAuFqIITQMAC3gmgF6O6l3JEA6qkZ+Y/de7cAAAAASUVORK5CYII=',
        wall=True
    ),
    'wall-right': Tile(
        id='',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAMklEQVQYV2MMDQ39'
            'z4AHMK4KZcCpYDVDKAMjSSaAdIQyrAZCBI1iBdEKYG4Gu4FiRwIA43Ue+WpSWc4AAAAASUVORK5CYII=',
        wall=True
    ),
    'wall-vertical': Tile(
        id='',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAG0lEQVQYV2MMDQ39'
            'H8qwmgEbWM0QysA4MhQAAD2TH/nrMiedAAAAAElFTkSuQmCC',
        wall=True
    ),
    'wall-corner-bottom-left': Tile(
        id='',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAANklEQVQYV2MMDQ39'
            'H8qwmgEbWM0QysCITwFIE1gBVu1QQQwTQMaCrITRpCuAWYfTBHT3EHQkAAj0IPmuXnNhAAAAAElFTkSuQmCC',
        wall=True
    ),
    'wall-corner-bottom-right': Tile(
        id='',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAPElEQVQYV2MMDQ39'
            'H8qwmgEbWM0QysC4KpThP1ZZoCBYAcgEXApA4mATQCpB1sBomAa4FUQrQLeKOo4EAB+iIPk9A4o5AAAAAElFTk'
            'SuQmCC',
        wall=True
    ),
    'wall-corner-top-left': Tile(
        id='',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAIUlEQVQYV2MMDQ39'
            'z4AHMIIUhDKsxqkEr4LVDKEMQ0IBAIgQHPlqSMNBAAAAAElFTkSuQmCC',
        wall=True
    ),
    'wall-corner-top-right': Tile(
        id='',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAJUlEQVQYV2MMDQ39'
            'z4AHMK4KZcCpYDVDKAMjyIRQhtVYzRgyCgBxZhz5QKrMXgAAAABJRU5ErkJggg==',
        wall=True
    )
}

class Game:
    """Game API.

    .. rooms:: rooms

       Rooms by ID.

    .. attribute:: data_path

       Path to data directory.
    """

    _SAVE_INTERVAL: ClassVar[timedelta] = timedelta(minutes=5)

    def __init__(self, *, data_path: PathLike[str] | str = 'data') -> None:
        self.rooms: dict[str, OnlineRoom] = {}
        self.data_path = Path(data_path)

    def create_room(self) -> OnlineRoom:
        """Create a new room."""
        blueprints = {
            blueprint.id:
                blueprint
                for blueprint in (
                    blueprint.model_copy(update={'id': randstr()}) # type: ignore[misc]
                    for blueprint in DEFAULT_BLUEPRINTS.values())
        }
        void = next(iter(blueprints.values()))
        room = OnlineRoom(id=randstr(), tile_ids=[void.id] * (OnlineRoom.SIZE ** 2),
                          blueprints=blueprints, version='0.1')
        self.rooms[room.id] = room
        return room

    async def run(self) -> NoReturn:
        """Run the game.

        If there is a problem reading from the data directory, an :exc:`OSError` is raised.
        """
        logger = getLogger(__name__)
        with timer() as t:
            for path in self.data_path.iterdir():
                room = OnlineRoom.model_validate_json(path.read_text(), strict=True)
                self.rooms[room.id] = room
        logger.info('Loaded %d room(s) (%.1fms)', len(self.rooms), t() * 1000)

        while True:
            # pylint: disable=broad-exception-caught
            await sleep(self._SAVE_INTERVAL.total_seconds())
            try:
                with timer() as t:
                    for room in self.rooms.values():
                        path = self.data_path / f'{room.id}.json'
                        path.write_bytes(_OfflineRoomModel.dump_json(room))
                logger.info('Saved %d room(s) (%.1fms)', len(self.rooms), t() * 1000)
            except OSError as e:
                logger.error('Failed to write to data directory (%s)', e)
            except Exception:
                logger.exception('Unhandled error')
