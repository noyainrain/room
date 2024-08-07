"""Game logic.

.. data:: AnyCause

   Any possible cause of a tile effect.

.. data:: AnyEffect

   Any possible tile effect.
"""

from __future__ import annotations

from asyncio import Queue, sleep
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from datetime import timedelta
import errno
from importlib import resources
from logging import getLogger
from os import PathLike
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated, ClassVar, Literal, NoReturn, Optional, TypeVar, Union, cast

from pydantic import (BaseModel, Field, PrivateAttr, TypeAdapter, computed_field, field_serializer,
                      field_validator, model_validator)

from . import context
from .effects import Cause, Effect, OpenDialogEffect
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
        return context.game.get().get_room(self.room_id)

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
AnyEffect = Annotated[Union[TransformTileEffect, OpenDialogEffect, FollowLinkEffect],
                      Field(discriminator='type')]

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
    version: Literal['0.6']

    @model_validator(mode='before')
    @classmethod
    def _check(cls, data: dict[str, object]) -> dict[str, object]:
        # Update version
        if data.get('version') in {None, '0.1', '0.2', '0.3', '0.4', '0.5'}:
            data['version'] = '0.6'

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

class OnlineRoom(OfflineRoom): # type: ignore[misc]
    """Creative space."""

    _members: list[Member] = PrivateAttr(default_factory=list)

    @property
    def members(self) -> Sequence[Member]:
        """Room members."""
        return self._members

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

class Overview(BaseModel): # type: ignore[misc]
    """Major game statistics.

    .. attribute:: players

       Number of players.

    .. attribute:: rooms

       Number of rooms.

    .. attribute:: online_rooms

       Number of rooms with online players.
    """

    players: int
    rooms: int
    online_rooms: int

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
        self.members: dict[str, Member] = {}
        self.data_path = Path(data_path)
        self._tokens: dict[str, PrivatePlayer] = {}
        self._rooms: dict[str, OnlineRoom] = {}
        self._room_template: OnlineRoom | None = None

    def _init_rooms(self) -> None:
        if 'origin' not in self._rooms:
            room = OnlineRoom.model_validate_json(
                (resources.files(f'{__package__}.res') / 'rooms' / 'origin.json').read_text(),
                strict=True)
            self._rooms['origin'] = room
            self._room_template = room.model_copy(deep=True)

    def get_room(self, room_id: str) -> OnlineRoom:
        """Get the room given by *room_id*."""
        self._init_rooms()
        return self._rooms[room_id]

    def get_overview(self) -> Overview:
        """Get major game statistics."""
        self._init_rooms()
        return Overview(
            players=len(self.players), rooms=len(self._rooms),
            online_rooms=sum(1 for room in self._rooms.values() if room.members))

    def sign_in(self) -> PrivatePlayer:
        """Sign in a player."""
        player = PrivatePlayer(id=randstr(), name='Guest', token=token_urlsafe(), tutorial=False)
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
        self._init_rooms()
        assert self._room_template
        blueprints = {
            blueprint_id: blueprint.model_copy(deep=True)
            for blueprint_id, blueprint in self._room_template.blueprints.items()
        }
        room = OnlineRoom(
            id=randstr(), title='New Room', description=None,
            tile_ids=list(self._room_template.tile_ids), blueprints=blueprints, version='0.6')
        self._rooms[room.id] = room
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
                self._rooms[room.id] = room
            # Reset Origin to ensure it is up-to-date
            self._rooms.pop('origin', None)
        logger.info('Loaded %d player(s) and %d room(s) (%.1fms)', len(self.players),
                    len(self._rooms), t() * 1000)

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
            for room in self._rooms.values():
                (rooms_path / f'{room.id}.json').write_bytes(
                    self._OfflineRoomModel.dump_json(room, indent=4))
        getLogger(__name__).info('Saved %d player(s) and %d room(s) (%.1fms)', len(self.players),
                                 len(self._rooms), t() * 1000)
