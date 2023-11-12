# pylint: disable=missing-docstring

import asyncio
from asyncio import create_task
from string import ascii_lowercase
from time import sleep
from unittest import IsolatedAsyncioTestCase, TestCase

from room.util import cancel, randstr, timer

class RandstrTest(TestCase):
    def test(self) -> None:
        string = randstr()
        self.assertEqual(len(string), 16)
        self.assertLessEqual(set(string), set(ascii_lowercase))

class CancelTest(IsolatedAsyncioTestCase):
    async def test(self) -> None:
        task = create_task(asyncio.sleep(1))
        await cancel(task)
        self.assertTrue(task.cancelled())

class TimerTest(TestCase):
    def test(self) -> None:
        with timer() as t:
            sleep(1 / 10)
        self.assertAlmostEqual(t(), 1 / 10, delta=1 / 20)
