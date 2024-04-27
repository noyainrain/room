# pylint: disable=missing-docstring

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase

from room import context
from room.game import (DEFAULT_BLUEPRINTS, FollowLinkEffect, Game, Link, Member, OnlineRoom, Tile,
                       TransformTileEffect, UseCause)

class TestCase(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.game = Game()
        context.game.set(self.game)
        self.player = self.game.sign_in()
        context.player.set(self.player)
        self.room = self.game.create_room()
        context.room.set(self.room)
        self._enter = self.room.enter()
        self.member = await self._enter.__aenter__()

    async def asyncTearDown(self) -> None:
        await self._enter.__aexit__(None, None, None)

class MemberTest(TestCase):
    async def test_perform_move_member_action(self) -> None:
        action = Member.MoveMemberAction(member_id=self.member.id, position=(1, 2))
        await action.perform()
        self.assertEqual(self.member.position, (1, 2))

class FollowLinkEffectTest(TestCase):
    async def test_apply(self) -> None:
        # effect = FollowLinkEffect(url='/foo/../bar') # relative
        # effect = FollowLinkEffect(url='https:/foo/../bar') # relative (same proto)
        # effect = FollowLinkEffect(url='ftp:/foo/../bar') # absolute (different proto)
        # effect = FollowLinkEffect(url='//example.org/foo/../bar') # absolute
        effect = FollowLinkEffect(url='https://example.org/')
        effect = await effect.apply(0)
        self.assertEqual(effect.link, Link(url=effect.url, title='Link'))

    async def test_apply_room_url(self) -> None:
        effect = FollowLinkEffect(url='/invites/meow')
        effect = await effect.apply(0)
        assert effect.link
        self.assertEqual(effect.link, Link(url=effect.url, title='Room #meow'))

    # OQ better name
    async def test_apply_relative_room_url(self) -> None:
        effect = FollowLinkEffect(url='')
        effect = await effect.apply(0)
        assert effect.link
        self.assertEqual(effect.link,
                         Link(url=f'/invites/{self.room.id}', title=f'Room #{self.room.id}'))

    async def test_apply_bad_room_url(self) -> None:
        effect = FollowLinkEffect(url='/foo')
        effect = await effect.apply(0)
        assert effect.link
        self.assertEqual(effect.link.title, 'Room')

class TransformTileEffectTest(TestCase):
    async def test_apply(self) -> None:
        effect = TransformTileEffect(blueprint_id='grass')
        await effect.apply(0)
        self.assertEqual(self.room.tiles[0], self.room.blueprints['grass'])

class TileTest(TestCase):
    async def test_cause(self) -> None:
        effects = await self.room.blueprints['wall-door-closed'].cause(UseCause(), 0)
        self.assertEqual(self.room.tiles[0], self.room.blueprints['wall-door-open'])
        self.assertEqual(effects,
                         [TransformTileEffect(blueprint_id='wall-door-open')]) # type: ignore[misc]

class RoomTest(TestCase):
    async def test_enter(self) -> None:
        async with self.room.enter() as member:
            self.assertIn(member, self.room.members)
            self.assertIn(member.id, self.game.members)
        self.assertNotIn(member, self.room.members)
        self.assertNotIn(member.id, self.game.members)

    async def test_perform_place_tile_action(self) -> None:
        action = OnlineRoom.PlaceTileAction(member_id=self.member.id, tile_index=0,
                                            blueprint_id='grass')
        await action.perform()
        self.assertEqual(self.room.tiles[0], self.room.blueprints['grass'])

    async def test_perform_use_action(self) -> None:
        place_tile_action = OnlineRoom.PlaceTileAction(member_id=self.member.id, tile_index=0,
                                                       blueprint_id='wall-door-closed')
        await place_tile_action.perform()
        action = OnlineRoom.UseAction(member_id=self.member.id, tile_index=0, effects=[])
        action = await action.perform()
        self.assertEqual(action.effects,
                         [TransformTileEffect(blueprint_id='wall-door-open')]) # type: ignore[misc]

    async def test_perform_update_blueprint_action(self) -> None:
        effects = {UseCause(): [TransformTileEffect(blueprint_id='void')]}
        void = self.room.blueprints['void'].model_copy(
            update={'wall': True, 'effects': effects}) # type: ignore[misc]
        action = OnlineRoom.UpdateBlueprintAction(member_id=self.member.id, blueprint=void)
        await action.perform()
        void = self.room.blueprints['void']
        self.assertEqual(void.image, DEFAULT_BLUEPRINTS['void'].image)
        self.assertTrue(void.wall)
        self.assertEqual(void.effects, effects)

    async def test_perform_update_blueprint_action_empty_id(self) -> None:
        action = OnlineRoom.UpdateBlueprintAction(
            member_id=self.member.id,
            blueprint=Tile(id='', image=self.room.blueprints['grass'].image, wall=False, effects={})
        )
        action = await action.perform()
        blueprint = self.room.blueprints.get(action.blueprint.id)
        assert blueprint
        self.assertEqual(blueprint.image, self.room.blueprints['grass'].image)
        self.assertFalse(blueprint.wall)
        self.assertFalse(blueprint.effects)

class GameTest(TestCase):
    def test_sign_in(self) -> None:
        player = self.game.sign_in()
        self.assertIn(player.id, self.game.players)

    def test_authenticate(self) -> None:
        player = self.game.authenticate(self.player.token)
        self.assertEqual(player, self.player)

    def test_authenticate_invalid_token(self) -> None:
        with self.assertRaises(LookupError):
            self.game.authenticate('foo')

    def test_create_room(self) -> None:
        room = self.game.create_room()
        self.assertIn(room.id, self.game.rooms)
        self.assertEqual(set(room.tile_ids), {'void'}) # type: ignore[misc]
        self.assertEqual(len(room.blueprints), len(DEFAULT_BLUEPRINTS))

    def test_create_data_directory(self) -> None:
        with TemporaryDirectory() as directory:
            game = Game(data_path=Path(directory) / 'data')
            game.create_data_directory()
            self.assertTrue((game.data_path / 'room').exists())

    def test_create_data_directory_existing_directory(self) -> None:
        with TemporaryDirectory() as directory:
            game = Game(data_path=directory)
            with self.assertRaises(FileExistsError):
                game.create_data_directory()
