"""Game logic.

.. data:: AnyCause

   Any possible cause of a tile effect.

.. data:: AnyEffect

   Any possible tile effect.

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
from typing import Annotated, ClassVar, Literal, NoReturn, TypeVar, Union

from pydantic import (BaseModel, Field, PrivateAttr, TypeAdapter, computed_field, field_serializer,
                      field_validator, model_validator)

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

class Cause(BaseModel): # type: ignore[misc]
    """Cause of a tile effect.

    .. attribute:: type

       Type of the cause.
    """

    type: str

    def __hash__(self) -> int:
        return hash(self.type)

class Effect(BaseModel): # type: ignore[misc]
    """Tile effect.

    .. attribute:: type

       Type of the effect.
    """

    type: str

    async def apply(self, tile_index: int) -> None:
        """Apply the effect to the tile at *tile_index*."""
        raise NotImplementedError()

class UseCause(Cause): # type: ignore[misc]
    """Cause of using a tile."""

    type: Literal['UseCause'] = 'UseCause'

class TransformTileEffect(Effect): # type: ignore[misc]
    """Effect of transforming a tile into another.

    .. attribute:: blueprint_id

       ID of the target form.
    """

    # Not nested in OnlineRoom to avoid circular dependency

    type: Literal['TransformTileEffect'] = 'TransformTileEffect'
    blueprint_id: str

    @property
    def blueprint(self) -> Tile:
        """Target form."""
        return context.room.get().blueprints[self.blueprint_id]

    async def apply(self, tile_index: int) -> None:
        context.room.get().tile_ids[tile_index] = self.blueprint_id

AnyCause = Annotated[Union[UseCause], Field(discriminator='type')]
AnyEffect = Annotated[Union[TransformTileEffect], Field(discriminator='type')]

class Tile(BaseModel): # type: ignore[misc]
    """Room tile.

    .. attribute:: id

       Unique tile ID.

    .. attribute:: image

       Image as data URL.

    .. attribute:: wall

       Indicates if the tile is impassable.

    .. attribute:: effects

       Tile effects by cause.

    .. attribute:: SIZE

       Tile width and height in px.
    """

    _EffectsItemModel: ClassVar[TypeAdapter[tuple[AnyCause, list[AnyEffect]]]] = (
        TypeAdapter(tuple[AnyCause, list[AnyEffect]])) # type: ignore[arg-type]

    SIZE: ClassVar[int] = 8

    id: str
    image: str
    wall: bool
    effects: dict[AnyCause, list[AnyEffect]]

    @model_validator(mode='before')
    @classmethod
    def _parse(cls, data: dict[str, object]) -> dict[str, object]:
        # Update effects (0.2)
        if 'effects' not in data:
            data['effects'] = []
        return data

    @field_validator('image')
    @classmethod
    def _check_image(cls, image: str) -> str:
        with open_image_data_url(image) as obj:
            if not obj.width == obj.height == cls.SIZE:
                raise ValueError(f'Bad image size {obj.width} x {obj.height} px')
        return image

    @field_validator('effects', mode='before')
    @classmethod
    def _parse_effects(cls, effects: object) -> object:
        if isinstance(effects, list):
            return dict(cls._EffectsItemModel.validate_python(item) for item in effects)
        return effects

    @field_validator('effects')
    @classmethod
    def _check_effects(cls,
                       effects: dict[AnyCause, list[AnyEffect]]) -> dict[AnyCause, list[AnyEffect]]:
        for cause, values in effects.items():
            if len(values) != len(set(type(effect) for effect in values)):
                raise ValueError(f'Duplicate effects for {cause.type}')
        return effects

    @field_serializer('effects')
    @classmethod
    def _dump_effects(cls, effects: dict[AnyCause, list[AnyEffect]]) -> object:
        return list(effects.items())

    async def cause(self, cause: AnyCause, tile_index: int) -> list[AnyEffect]:
        """Apply the effects of a *cause* to the tile at *tile_index*."""
        # Note that if there is a crash applying an effect, subsequent effects will not be applied
        effects = self.effects.get(cause) or []
        for effect in effects:
            await effect.apply(tile_index)
        return effects

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

    .. attribute:: WIDTH

       Room width.

    .. attribute:: HEIGHT

       Room height.
    """

    SIZE: ClassVar[int] = 8
    WIDTH: ClassVar[int] = SIZE
    HEIGHT: ClassVar[int] = SIZE

    id: str
    tile_ids: list[str]
    blueprints: dict[str, Tile]
    version: Literal['0.2']

    @model_validator(mode='before')
    @classmethod
    def _check(cls, data: dict[str, object]) -> dict[str, object]:
        # Update version
        if data.get('version') in {None, '0.1'}:
            data['version'] = '0.2'
        return data

    @property
    def tiles(self) -> list[Tile]:
        """Grid of room tiles, serialized in row direction."""
        return [self.blueprints[tile_id] for tile_id in self.tile_ids]

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

    class PlaceTileAction(Action): # type: ignore[misc]
        """Action of placing a tile.

        .. attribute:: tile_index

           Index of the target tile.

        .. attribute:: blueprint_id

           ID of the blueprint to place.
        """

        tile_index: int
        blueprint_id: str

        @property
        def tile(self) -> Tile:
            """Target tile."""
            return context.room.get().tiles[self.tile_index]

        @property
        def blueprint(self) -> Tile:
            """Blueprint to place."""
            return context.room.get().blueprints[self.blueprint_id]

        async def perform(self) -> OnlineRoom.PlaceTileAction:
            room = context.room.get()
            # Use property to check blueprint ID
            room.tile_ids[self.tile_index] = self.blueprint.id
            await room.publish(self)
            return self

    class UseAction(Action): # type: ignore[misc]
        """Action of using a tile.

        .. attribute:: tile_index

           Index of the used tile.

        .. attribute:: effects

           Caused tile effects.
        """

        tile_index: int
        effects: list[AnyEffect]

        @property
        def tile(self) -> Tile:
            """Target tile."""
            return context.room.get().tiles[self.tile_index]

        async def perform(self) -> OnlineRoom.UseAction:
            effects = await self.tile.cause(UseCause(), self.tile_index)
            action = self.model_copy(update={'effects': effects}) # type: ignore[misc]
            await context.room.get().publish(action)
            return action

    class UpdateBlueprintAction(Action): # type: ignore[misc]
        """Action of updating a tile blueprint.

        If :attr:`blueprint` *id* is empty, a new blueprint is created.

        .. attribute:: blueprint

           Updated tile blueprint.
        """

        blueprint: Tile

        async def perform(self) -> OnlineRoom.UpdateBlueprintAction:
            room = context.room.get()
            for effects in self.blueprint.effects.values():
                for effect in effects:
                    if isinstance(effect, TransformTileEffect):
                        # pylint: disable=pointless-statement
                        # Check blueprint ID
                        effect.blueprint
            if self.blueprint.id:
                # pylint: disable=pointless-statement
                # Check blueprint ID
                room.blueprints[self.blueprint.id]
                action = self
            else:
                blueprint = self.blueprint.model_copy(update={'id': randstr()}) # type: ignore[misc]
                action = self.model_copy(update={'blueprint': blueprint}) # type: ignore[misc]
            room.blueprints[action.blueprint.id] = action.blueprint
            await room.publish(action)
            return action

DEFAULT_BLUEPRINTS = {
    'void': Tile(
        id='void',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAKElEQVQYV2NkYGD4'
            'D8Q4ASNIQWhoKMPq1atRFMHEwAoImkAHBRQ5EgCbrhQB2kRr+QAAAABJRU5ErkJggg==',
        wall=False,
        effects={}
    ),
    'grass': Tile(
        id='grass',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAOElEQVQYV2NkWMXw'
            'nwEPYAQpCA0NZVi9ejVWZRgK0BWDFSBrJagA3R64Ceg6YXycCmAmYbgB3QoAnmIiUcgpwTgAAAAASUVORK5CYI'
            'I=',
        wall=False,
        effects={}
    ),
    'floor': Tile(
        id='floor',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFElEQVQYV2NctWrV'
            'fwY8gHFkKAAApMMX8a16WAwAAAAASUVORK5CYII=',
        wall=False,
        effects={}
    ),
    'wall-horizontal': Tile(
        id='wall-horizontal',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAALElEQVQYV2MMDQ39'
            'z4AHMK4KZcCvgGgTVjOEAuFqIITQMAC3gmgF6O6l3JEA6qkZ+Y/de7cAAAAASUVORK5CYII=',
        wall=True,
        effects={}
    ),
    'wall-horizontal-left': Tile(
        id='wall-horizontal-left',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAANUlEQVQYV2MMDQ39'
            'z4AHMIIUhDKsxqkErIBoE1YzhALhaiCE0CCAYgVBBTCrcJqAzS0EHQkARNYe+TqxIDUAAAAASUVORK5CYII=',
        wall=True,
        effects={}
    ),
    'wall-horizontal-right': Tile(
        id='wall-horizontal-right',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAMklEQVQYV2MMDQ39'
            'z4AHMK4KZcCpYDVDKAMjSSaAdIQyrAZCBI1iBdEKYG4Gu4FiRwIA43Ue+WpSWc4AAAAASUVORK5CYII=',
        wall=True,
        effects={}
    ),
    'wall-vertical': Tile(
        id='wall-vertical',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAG0lEQVQYV2MMDQ39'
            'H8qwmgEbWM0QysA4MhQAAD2TH/nrMiedAAAAAElFTkSuQmCC',
        wall=True,
        effects={}
    ),
    'wall-corner-bottom-left': Tile(
        id='wall-corner-bottom-left',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAANklEQVQYV2MMDQ39'
            'H8qwmgEbWM0QysCITwFIE1gBVu1QQQwTQMaCrITRpCuAWYfTBHT3EHQkAAj0IPmuXnNhAAAAAElFTkSuQmCC',
        wall=True,
        effects={}
    ),
    'wall-corner-bottom-right': Tile(
        id='wall-corner-bottom-right',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAPElEQVQYV2MMDQ39'
            'H8qwmgEbWM0QysC4KpThP1ZZoCBYAcgEXApA4mATQCpB1sBomAa4FUQrQLeKOo4EAB+iIPk9A4o5AAAAAElFTk'
            'SuQmCC',
        wall=True,
        effects={}
    ),
    'wall-corner-top-left': Tile(
        id='wall-corner-top-left',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAIUlEQVQYV2MMDQ39'
            'z4AHMIIUhDKsxqkEr4LVDKEMQ0IBAIgQHPlqSMNBAAAAAElFTkSuQmCC',
        wall=True,
        effects={}
    ),
    'wall-corner-top-right': Tile(
        id='wall-corner-top-right',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAJUlEQVQYV2MMDQ39'
            'z4AHMK4KZcCpYDVDKAMjyIRQhtVYzRgyCgBxZhz5QKrMXgAAAABJRU5ErkJggg==',
        wall=True,
        effects={}
    ),
    'wall-door-closed': Tile(
        id='wall-door-closed',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAKUlEQVQYV2MMDQ39'
            'z4AHMK4KZcCvgHITCFqBTcFqhlCws0MZVjNQ7kgAqm0R+QmF/X4AAAAASUVORK5CYII=',
        wall=True,
        effects={UseCause(): [TransformTileEffect(blueprint_id='wall-door-open')]}
    ),
    'wall-door-open': Tile(
        id='wall-door-open',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAKUlEQVQYV2MMDQ39'
            'zwAEQBpEYQDGVaEM/1czhOJWQLkJBK2gXAEhRwIAATAc8UKSQEIAAAAASUVORK5CYII=',
        wall=False,
        effects={UseCause(): [TransformTileEffect(blueprint_id='wall-door-closed')]}
    ),
    'wall-lamp-off': Tile(
        id='wall-lamp-off',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAQklEQVQYV41PWwoA'
            'MAiyQ3rJPORWwQaDvYR+zNSMZMMF5sRd8O0gEO4OSTWEKnhGJBVuRW4FtQhRYlwvDqdH7FWyA4jCHvmIXOL4AA'
            'AAAElFTkSuQmCC',
        wall=True,
        effects={UseCause(): [TransformTileEffect(blueprint_id='wall-lamp-on')]}
    ),
    'wall-lamp-on': Tile(
        id='wall-lamp-on',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAQ0lEQVQYV42OQRIA'
            'IAgC6ZH4SH1khY2HLhknZlyQQXLioeHEG/hq4K4xA9zPr/JhgXzRAkoVJK8mpaVrpCCpjgl0IxdRtCX5PJx3Mg'
            'AAAABJRU5ErkJggg==',
        wall=True,
        effects={UseCause(): [TransformTileEffect(blueprint_id='wall-lamp-off')]}
    )
}

class Game:
    """Game API.

    .. rooms:: rooms

       Rooms by ID.

    .. attribute:: data_path

       Path to data directory.
    """

    _OfflineRoomModel: ClassVar[TypeAdapter[OfflineRoom]] = TypeAdapter(OfflineRoom)

    _SAVE_INTERVAL: ClassVar[timedelta] = timedelta(minutes=5)

    def __init__(self, *, data_path: PathLike[str] | str = 'data') -> None:
        self.rooms: dict[str, OnlineRoom] = {}
        self.data_path = Path(data_path)

    def create_room(self) -> OnlineRoom:
        """Create a new room."""
        blueprints = {
            blueprint.id: blueprint.model_copy() for blueprint in DEFAULT_BLUEPRINTS.values()
        }
        room = OnlineRoom(
            id=randstr(), tile_ids=['void'] * (OfflineRoom.WIDTH * OfflineRoom.HEIGHT),
            blueprints=blueprints, version='0.2')
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
                        path.write_bytes(self._OfflineRoomModel.dump_json(room))
                logger.info('Saved %d room(s) (%.1fms)', len(self.rooms), t() * 1000)
            except OSError as e:
                logger.error('Failed to write to data directory (%s)', e)
            except Exception:
                logger.exception('Unhandled error')
