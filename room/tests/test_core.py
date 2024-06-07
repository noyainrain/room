# pylint: disable=missing-docstring

from room.core import PrivatePlayer

from .test_game import TestCase

class PrivatePlayerTest(TestCase):
    def test_update(self) -> None:
        self.player.update(PrivatePlayer(id='', token='', tutorial=True))
        self.assertTrue(self.player.tutorial)
