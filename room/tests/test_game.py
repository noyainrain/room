# pylint: disable=missing-docstring

from unittest import IsolatedAsyncioTestCase

from room import context
from room.game import DEFAULT_BLUEPRINTS, Game, OnlineRoom, Player, Tile

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

class RoomTest(TestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        blueprints = iter(self.room.blueprints.values())
        self.blueprints = {'void': next(blueprints), 'grass': next(blueprints)}

    async def test_join(self) -> None:
        async with self.room.join() as player:
            self.assertIn(player.id, self.room.players)
        self.assertNotIn(player.id, self.room.players)

    async def test_perform_use_action(self) -> None:
        action = OnlineRoom.UseAction(player_id=self.player.id, tile_index=0,
                                      item_id=self.blueprints['grass'].id)
        await action.perform()
        self.assertEqual(self.room.tiles[0].id, self.blueprints['grass'].id)

    async def test_perform_update_blueprint_action(self) -> None:
        void = self.blueprints['void'].model_copy(update={'wall': True}) # type: ignore[misc]
        action = OnlineRoom.UpdateBlueprintAction(player_id=self.player.id, blueprint=void)
        await action.perform()
        void = self.room.blueprints[void.id]
        self.assertEqual(void.image, self.blueprints['void'].image)
        self.assertTrue(void.wall)

    async def test_perform_update_blueprint_action_empty_id(self) -> None:
        action = OnlineRoom.UpdateBlueprintAction(
            player_id=self.player.id,
            blueprint=Tile(id='', image=self.blueprints['grass'].image, wall=False))
        action = await action.perform()
        blueprint = self.room.blueprints.get(action.blueprint.id)
        assert blueprint
        self.assertEqual(blueprint.image, self.blueprints['grass'].image)
        self.assertFalse(blueprint.wall)

class GameTest(TestCase):
    def test_create_room(self) -> None:
        room = self.game.create_room()
        self.assertIn(room.id, self.game.rooms)
        self.assertEqual(len(room.tiles), OnlineRoom.SIZE ** 2)
        self.assertEqual(len(room.blueprints), len(DEFAULT_BLUEPRINTS))
