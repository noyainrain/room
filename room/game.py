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
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from datetime import timedelta
import errno
from logging import getLogger
from os import PathLike
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated, ClassVar, Literal, NoReturn, Optional, TypeVar, Union, cast

from pydantic import (BaseModel, Field, PrivateAttr, TypeAdapter, computed_field, field_serializer,
                      field_validator, model_validator)

from . import context
from .core import Player, PrivatePlayer, Text
from .util import open_image_data_url, randstr, timer

A = TypeVar('A', bound='Action')

class Action(BaseModel): # type: ignore[misc]
    """Action by a room member.

    .. attribute:: member_id

       ID of the room member performing the action.
    """

    member_id: str

    @computed_field # type: ignore[misc]
    @property
    def type(self) -> str:
        """Type of the action."""
        return type(self).__name__

    @property
    def member(self) -> Member:
        """Room member performing the action."""
        return context.game.get().members[self.member_id]

    async def perform(self: A) -> A:
        """Perform the action.

        An action with result information is returned.

        May be overridden by subclass. By default, self is returned.
        """
        return self

class FailedAction(Action): # type: ignore[misc]
    """Failed action.

    .. attribute:: message

       Error message.
    """

    message: str

class Member(BaseModel): # type: ignore[misc]
    """Player as member of a room.

    .. attribute:: id

       Unique member ID.

    .. attribute:: player_id

       Relevant player ID.

    .. attribute:: room_id

       Relevant room ID.

    .. attribute:: position

       Current position in px.
    """

    id: str
    player_id: str
    room_id: str
    position: tuple[float, float]
    _queue: Queue[Action] = PrivateAttr(default_factory=Queue)

    @property
    def player(self) -> Player:
        """Relevant player."""
        return context.game.get().players[self.player_id]

    @property
    def room(self) -> OnlineRoom:
        """Relevant room."""
        return context.game.get().rooms[self.room_id]

    async def actions(self) -> AsyncGenerator[Action, None]:
        """Stream of actions intended for the member."""
        while True:
            yield await self._queue.get()

    async def publish(self, action: Action) -> None:
        """Publish an *action* to the member."""
        await self._queue.put(action)

    def with_player(self) -> MemberWithPlayer:
        """Create a copy of the member with player included."""
        return MemberWithPlayer(id=self.id, player_id=self.player_id, room_id=self.room_id,
                                position=self.position)

    class MoveMemberAction(Action): # type: ignore[misc]
        """Action of moving the room member.

        .. attribute:: position

           Target position.
        """

        position: tuple[float, float]

        async def perform(self) -> Member.MoveMemberAction:
            room = context.room.get()
            if (
                not (0 <= self.position[0] < room.WIDTH * Tile.SIZE and
                     0 <= self.position[1] < room.HEIGHT * Tile.SIZE)
            ):
                raise ValueError(f'Out-of-range position {self.position}')
            self.member.position = self.position
            await room.publish(self)
            return self

class MemberWithPlayer(Member): # type: ignore[misc]
    """Room member with player included."""

    @computed_field # type: ignore[misc]
    @property
    def player(self) -> Player:
        return super().player

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

    async def apply(self, tile_index: int) -> Effect:
        """Apply the effect to the tile at *tile_index*.

        The applied effect with concrete result details is returned.
        """
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

    async def apply(self, tile_index: int) -> TransformTileEffect:
        context.room.get().tile_ids[tile_index] = self.blueprint_id
        return self

class Link(BaseModel): # type: ignore[misc]
    """Web link.

    .. attribute:: url

       Link URL.

    .. attribute:: title

       Link title.
    """

    # The base for relative URLs is where the room is served, e.g. https://example.org/rooms/abc or
    # file:/home/frank/abc.json. Conceptually, rooms are mapped to a familiar web address via link
    # tag:
    # <link
    #     rel="alternate" type="application/vnd.room+json" href="https://example.org/api/rooms/abc"
    # />

    url: str
    title: Text

class FollowLinkEffect(Effect): # type: ignore[misc]
    """Effect of following a link.

    .. attribute:: url

       Link URL.

    .. attribute:: link

       Followed link.
    """

    type: Literal['FollowLinkEffect'] = 'FollowLinkEffect'
    url: str
    link: Optional[Link]

    async def apply(self, tile_index: int) -> FollowLinkEffect:
        link = Link(url=self.url, title='Link')
        return self.model_copy(update={'link': link}) # type: ignore[misc]

AnyCause = Annotated[Union[UseCause], Field(discriminator='type')]
AnyEffect = Annotated[Union[TransformTileEffect, FollowLinkEffect], Field(discriminator='type')]

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
        TypeAdapter(tuple[AnyCause, list[AnyEffect]]))

    SIZE: ClassVar[int] = 8

    id: str
    image: str
    wall: bool
    effects: dict[AnyCause, Annotated[list[AnyEffect], Field(min_length=1)]]

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

    @field_serializer('effects')
    @classmethod
    def _dump_effects(cls, effects: dict[AnyCause, list[AnyEffect]]) -> object:
        return list(effects.items())

    async def cause(self, cause: AnyCause, tile_index: int) -> list[AnyEffect]:
        """Apply the effects of a *cause* to the tile at *tile_index*."""
        # Note that if there is a crash applying an effect, subsequent effects will not be applied
        effects = self.effects.get(cause) or []
        return [await effect.apply(tile_index) for effect in effects]

class BaseRoom(BaseModel): # type: ignore[misc]
    """Room basis.

    .. attribute:: id

       Unique room ID.

    .. attribute:: title

       Room title.

    .. attribute:: description

       Room description.
    """

    id: str
    title: Text
    description: Optional[Text]

class OfflineRoom(BaseRoom): # type: ignore[misc]
    """Room file.

    .. attribute:: tile_ids

       Grid of room tiles, referenced by ID, serialized in row direction.

    .. attribute:: blueprints

       Tile blueprints by ID.

    .. attribute:: version

       Room file version.

    .. attribute:: WIDTH

       Room width.

    .. attribute:: HEIGHT

       Room height.

    .. attribute:: MEDIA_TYPE

       Room file media type.
    """

    WIDTH: ClassVar[int] = 16
    HEIGHT: ClassVar[int] = 9
    MEDIA_TYPE: ClassVar[str] = 'application/vnd.room+json'

    tile_ids: Annotated[list[str], Field(min_length=WIDTH * HEIGHT, max_length=WIDTH * HEIGHT)]
    blueprints: dict[str, Tile]
    version: Literal['0.5']

    @model_validator(mode='before')
    @classmethod
    def _check(cls, data: dict[str, object]) -> dict[str, object]:
        # Update version
        if data.get('version') in {None, '0.1', '0.2', '0.3', '0.4'}:
            data['version'] = '0.5'

        # Update size (0.3)
        source = data.get('tile_ids')
        assert isinstance(source, list), f'Bad tile_ids type {type(source)}'
        if len(source) == (source_width := 8) * (source_height := 8):
            blueprints = data.get('blueprints')
            assert isinstance(blueprints, dict), f'Bad blueprints type {type(blueprints)}'
            try:
                void_id = next(iter(cast(dict[str, object], blueprints)))
            except StopIteration:
                raise AssertionError('Empty blueprints') from None

            tile_ids = [void_id] * cls.WIDTH * cls.HEIGHT
            offset = ((cls.WIDTH - source_width) // 2, (cls.HEIGHT - source_height) // 2)
            for y in range(0, source_height):
                source_i = y * source_width
                i = offset[0] + (y + offset[1]) * cls.WIDTH
                tile_ids[i:i + source_width] = source[source_i:source_i + source_width]
            data['tile_ids'] = tile_ids

        # Update details (0.4)
        if 'title' not in data:
            data['title'] = 'New Room'
        if 'description' not in data:
            data['description'] = None

        return data

    @property
    def tiles(self) -> list[Tile]:
        """Grid of room tiles, serialized in row direction."""
        return [self.blueprints[tile_id] for tile_id in self.tile_ids]

import PIL.Image
from PIL.Image import Image
from io import BytesIO
from base64 import b64encode

class OnlineRoom(OfflineRoom): # type: ignore[misc]
    """Creative space."""

    _members: list[Member] = PrivateAttr(default_factory=list)

    @property
    def members(self) -> Sequence[Member]:
        """Room members."""
        return self._members

    async def get_image(self) -> bytes:
        """TODO."""
        #path = Path('data-images')
        #path.mkdir(exist_ok=True)
        #for room in self.rooms.values():
        with timer() as t:
            cache: dict[str, Image] = {}
            image = PIL.Image.new('RGBA', (self.WIDTH * Tile.SIZE, self.HEIGHT * Tile.SIZE))
            tiles = self.tiles

            for y in range(self.HEIGHT):
                for x in range(self.WIDTH):
                    i = x + y * self.WIDTH
                    tile = tiles[i]

                    try:
                        obj = cache[tile.image]
                    except KeyError:
                        obj = cache[tile.image] = open_image_data_url(tile.image)

                    #with open_image_data_url(tile.image) as obj:
                    #    image.paste(obj, (x * Tile.SIZE, y * Tile.SIZE))
                    image.paste(obj, (x * Tile.SIZE, y * Tile.SIZE))

            # image.save(path / f'{room.id}.png')
            stream = BytesIO()
            image.save(stream, format='PNG')
            #print(f'data:image/png;base64,{b64encode(stream.getvalue()).decode()}')

        print('RENDERED IMG', t() * 1000, 'ms', 'TILES IN CACHE', len(cache))
        return stream.getvalue()

    @asynccontextmanager
    async def enter(self) -> AsyncGenerator[Member, None]:
        """Context manager to enter the room as member.

        On exit also exit the room again.
        """
        game = context.game.get()
        member = game.create_member(self)
        await self.publish(Member.MoveMemberAction(member_id=member.id, position=member.position))
        await member.publish(self.WelcomeAction(member_id=member.id, room=self.with_members()))
        yield member

        game.delete_member(member)
        await self.publish(Member.MoveMemberAction(member_id=member.id, position=(-1, -1)))

    async def publish(self, action: Action) -> None:
        """Publish an *action* to all members."""
        for member in self._members:
            await member.publish(action)

    def with_members(self) -> OnlineRoomWithMembers:
        """Create a copy of the room with members included."""
        room = OnlineRoomWithMembers(
            id=self.id, title=self.title, description=self.description, tile_ids=self.tile_ids,
            blueprints=self.blueprints, version=self.version)
        room._members = self._members
        return room

    def link_member(self, member: Member) -> None:
        """Link an existing *member*."""
        if not member.room_id == self.id:
            raise ValueError(f'Alien member room_id {member.room_id}')
        self._members.append(member)

    def unlink_member(self, member: Member) -> None:
        """Unlink a *member*."""
        try:
            self._members.remove(member)
        except ValueError:
            raise LookupError(member.id) from None

    class WelcomeAction(Action): # type: ignore[misc]
        """Handshake action.

        .. attribute:: room

           Joined room.
        """

        room: OnlineRoomWithMembers

    class UpdateRoomAction(Action): # type: ignore[misc]
        """Action of updating room details.

        .. attribute:: room

           Updated room basis.
        """

        room: BaseRoom

        async def perform(self) -> OnlineRoom.UpdateRoomAction:
            room = context.room.get()
            if self.room.id != room.id:
                raise ValueError(f'External room {self.room.id}')
            room.title = self.room.title
            room.description = self.room.description
            await room.publish(self)
            return self

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

class OnlineRoomWithMembers(OnlineRoom): # type: ignore[misc]
    """Room with members included."""

    @computed_field # type: ignore[misc]
    @property
    def members(self) -> Sequence[MemberWithPlayer]:
        """Room members."""
        return [member.with_player() for member in self._members]

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
    ),
    'wall-board': Tile(
        id='wall-board',
        image=
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAQElEQVQYV2MMDQ39'
            'z4AHMK4KZcCvgHITQFaEroLYsjqMEUyHAgUh/NUMYDfAFaxeDRLFVADVBvELUAEyYCTkSAC7zB/5tkwb/wAAAA'
            'BJRU5ErkJggg==',
        wall=True,
        effects={UseCause(): [FollowLinkEffect(url='https://discord.gg/Jey5jCJy2T', link=None)]}
    )
}

class Game:
    """Game API.

    .. attribute:: players

       Players by ID.

    .. rooms:: rooms

       Rooms by ID.

    .. attribute:: members

       Room members by ID.

    .. attribute:: data_path

       Path to data directory.
    """

    _OfflineRoomModel: ClassVar[TypeAdapter[OfflineRoom]] = TypeAdapter(OfflineRoom)

    _SAVE_INTERVAL: ClassVar[timedelta] = timedelta(minutes=5)

    def __init__(self, *, data_path: PathLike[str] | str = 'data') -> None:
        self.players: dict[str, PrivatePlayer] = {}
        self.rooms: dict[str, OnlineRoom] = {}
        self.members: dict[str, Member] = {}
        self.data_path = Path(data_path)
        self._tokens: dict[str, PrivatePlayer] = {}

    def sign_in(self) -> PrivatePlayer:
        """Sign in a player."""
        player = PrivatePlayer(id=randstr(), token=token_urlsafe(), tutorial=False)
        self._add_player(player)
        return player

    def _add_player(self, player: PrivatePlayer) -> None:
        self.players[player.id] = player
        self._tokens[player.token] = player

    def authenticate(self, token: str) -> PrivatePlayer:
        """Authenticate a player with *token*.

        If authentication fails, a :exc:`LookupError` is raised.
        """
        return self._tokens[token]

    def create_room(self) -> OnlineRoom:
        """Create a new room."""
        blueprints = {
            blueprint.id: blueprint.model_copy() for blueprint in DEFAULT_BLUEPRINTS.values()
        }
        room = OnlineRoom(
            id=randstr(), title='New Room', description=None,
            tile_ids=['void'] * (OfflineRoom.WIDTH * OfflineRoom.HEIGHT), blueprints=blueprints,
            version='0.5')
        self.rooms[room.id] = room
        return room

    def create_member(self, room: OnlineRoom) -> Member:
        """Create a new *room* member."""
        member = Member(id=randstr(), player_id=context.player.get().id, room_id=room.id,
                        position=(room.WIDTH * Tile.SIZE / 2, room.HEIGHT * Tile.SIZE / 2))
        self.members[member.id] = member
        room.link_member(member)
        return member

    def delete_member(self, member: Member) -> None:
        """Delete a room *member*."""
        del self.members[member.id]
        member.room.unlink_member(member)

    def create_data_directory(self) -> None:
        """Create the data directory at :attr:`data_path`.

        If there is a problem creating the directory, an :exc:`OSError` is raised, most notably a
        :exc:`FileExistsError` if it already exists.
        """
        self.data_path.mkdir()
        self._save()
        (self.data_path / 'room').touch()

    async def run(self) -> NoReturn:
        """Run the game.

        If there is a problem reading from the data directory, an :exc:`OSError` is raised.
        """
        # Update marker
        if all(path.match('*.json') for path in self.data_path.iterdir()):
            (self.data_path / 'room').touch()

        if not (self.data_path / 'room').exists():
            raise OSError(errno.EINVAL, 'Bad Room data directory')

        # Update players
        state_path = self.data_path / 'state'
        state_path.mkdir(exist_ok=True)
        (state_path / 'players').mkdir(exist_ok=True)
        rooms_path = state_path / 'rooms'
        rooms_path.mkdir(exist_ok=True)
        for path in self.data_path.glob('*.json'):
            path.rename(rooms_path / path.name)

        logger = getLogger(__name__)

        with timer() as t:
            state_path = self.data_path / 'state'
            for path in (state_path / 'players').iterdir():
                self._add_player(PrivatePlayer.model_validate_json(path.read_text(), strict=True))
            for path in (state_path / 'rooms').iterdir():
                room = OnlineRoom.model_validate_json(path.read_text(), strict=True)
                self.rooms[room.id] = room
        logger.info('Loaded %d player(s) and %d room(s) (%.1fms)', len(self.players),
                    len(self.rooms), t() * 1000)

        while True:
            # pylint: disable=broad-exception-caught
            try:
                await sleep(self._SAVE_INTERVAL.total_seconds())
            finally:
                # Also save on exit, i.e. when the task is cancelled
                try:
                    self._save()
                except OSError as e:
                    logger.error('Failed to write to data directory (%s)', e)
                except Exception:
                    logger.exception('Unhandled error')

    def _save(self) -> None:
        with timer() as t:
            state_path = self.data_path / 'state'
            state_path.mkdir(exist_ok=True)

            players_path = state_path / 'players'
            players_path.mkdir(exist_ok=True)
            for player in self.players.values():
                (players_path / f'{player.id}.json').write_text(player.model_dump_json())

            rooms_path = state_path / 'rooms'
            rooms_path.mkdir(exist_ok=True)
            for room in self.rooms.values():
                (rooms_path / f'{room.id}.json').write_bytes(self._OfflineRoomModel.dump_json(room))
        getLogger(__name__).info('Saved %d player(s) and %d room(s) (%.1fms)', len(self.players),
                                 len(self.rooms), t() * 1000)
