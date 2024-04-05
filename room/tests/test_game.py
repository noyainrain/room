# pylint: disable=missing-docstring

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase

from room import context
from room.game import (DEFAULT_BLUEPRINTS, Game, OnlineRoom, Player, Tile, TransformTileEffect,
                       UseCause)

class TestCase(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.game = Game()
        self.room = self.game.create_room()
        context.room.set(self.room)
        self._join = self.room.join()
        self.player = await self._join.__aenter__()

    async def asyncTearDown(self) -> None:
        await self._join.__aexit__(None, None, None)

class PlayerTest(TestCase):
    async def test_perform_move_player_action(self) -> None:
        action = Player.MovePlayerAction(player_id=self.player.id, position=(1, 2))
        await action.perform()
        self.assertEqual(self.player.position, (1, 2))

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
    async def test_join(self) -> None:
        async with self.room.join() as player:
            self.assertIn(player.id, self.room.players)
        self.assertNotIn(player.id, self.room.players)

    async def test_perform_place_tile_action(self) -> None:
        action = OnlineRoom.PlaceTileAction(player_id=self.player.id, tile_index=0,
                                            blueprint_id='grass')
        await action.perform()
        self.assertEqual(self.room.tiles[0], self.room.blueprints['grass'])

    async def test_perform_use_action(self) -> None:
        place_tile_action = OnlineRoom.PlaceTileAction(player_id=self.player.id, tile_index=0,
                                                       blueprint_id='wall-door-closed')
        await place_tile_action.perform()
        action = OnlineRoom.UseAction(player_id=self.player.id, tile_index=0, effects=[])
        action = await action.perform()
        self.assertEqual(action.effects,
                         [TransformTileEffect(blueprint_id='wall-door-open')]) # type: ignore[misc]

    async def test_perform_update_blueprint_action(self) -> None:
        effects = {UseCause(): [TransformTileEffect(blueprint_id='void')]}
        void = self.room.blueprints['void'].model_copy(
            update={'wall': True, 'effects': effects}) # type: ignore[misc]
        action = OnlineRoom.UpdateBlueprintAction(player_id=self.player.id, blueprint=void)
        await action.perform()
        void = self.room.blueprints['void']
        self.assertEqual(void.image, DEFAULT_BLUEPRINTS['void'].image)
        self.assertTrue(void.wall)
        self.assertEqual(void.effects, effects)

    async def test_perform_update_blueprint_action_empty_id(self) -> None:
        action = OnlineRoom.UpdateBlueprintAction(
            player_id=self.player.id,
            blueprint=Tile(id='', image=self.room.blueprints['grass'].image, wall=False, effects={})
        )
        action = await action.perform()
        blueprint = self.room.blueprints.get(action.blueprint.id)
        assert blueprint
        self.assertEqual(blueprint.image, self.room.blueprints['grass'].image)
        self.assertFalse(blueprint.wall)
        self.assertFalse(blueprint.effects)

class GameTest(TestCase):
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
