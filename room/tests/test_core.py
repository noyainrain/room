# pylint: disable=missing-docstring

from .test_game import TestCase

class PrivatePlayerTest(TestCase):
    def test_update(self) -> None:
        patch = self.player.model_copy(
            update={'name': 'Frank', 'tutorial': True}) # type: ignore[misc]
        self.player.update(patch)
        self.assertEqual(self.player.name, 'Frank')
        self.assertTrue(self.player.tutorial)
