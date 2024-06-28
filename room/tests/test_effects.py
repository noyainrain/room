# pylint: disable=missing-docstring

from room.effects import OpenDialogEffect

from .test_game import TestCase

class OpenDialogEffectTest(TestCase):
    async def test_apply(self) -> None:
        effect = OpenDialogEffect(message='Meow!')
        applied = await effect.apply(0)
        self.assertEqual(applied.message, effect.message)
