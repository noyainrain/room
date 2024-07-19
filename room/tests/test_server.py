# pylint: disable=missing-docstring

from __future__ import annotations

from typing import TypeVar

from aiohttp import ClientSession
from pydantic import BaseModel

from room.core import PrivatePlayer
from room.game import OnlineRoom
from room.server import serve

from .test_game import TestCase

M = TypeVar('M', bound=BaseModel)

class ServerTestCase(TestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.server = await serve(self.game, host='localhost', port=16160)

    async def asyncTearDown(self) -> None:
        await self.server.aclose()
        await super().asyncTearDown()

    async def request(self, method: str, url: str, model: type[M], *,
                      obj: BaseModel | None = None) -> M:
        async with ClientSession(self.server.url, raise_for_status=True) as client:
            data = obj.model_dump_json() if obj else None
            async with client.request(method, url, data=data) as response:
                return model.model_validate_json(await response.read(), strict=True)

class PutCurrentPlayerTest(ServerTestCase):
    async def test(self) -> None:
        patch = self.player.model_copy(update={'tutorial': True}) # type: ignore[misc]
        player = await self.request('PUT', '/api/players/self', PrivatePlayer, obj=patch)
        self.assertTrue(player.tutorial)

class PostRoomTest(ServerTestCase):
    async def test(self) -> None:
        room = await self.request('POST', '/api/rooms', OnlineRoom)
        self.assertEqual(room.title, 'New Room')

class GetRoomTest(ServerTestCase):
    async def test(self) -> None:
        room = await self.request('GET', f'/api/rooms/{self.room.id}', OnlineRoom)
        self.assertEqual(room.id, self.room.id)
