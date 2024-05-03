# pylint: disable=missing-docstring

import asyncio
from asyncio import create_task
from string import ascii_lowercase
from textwrap import dedent
from time import sleep
from unittest import IsolatedAsyncioTestCase, TestCase

from room.util import Router, cancel, randstr, template, timer

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

class TemplateTest(TestCase):
    def test_call(self) -> None:
        t = template(f'{__package__}.res', 'template.md')
        text = t(message='Meow!')
        self.assertEqual(
            text,
            dedent(
                """\
                # Cat

                The cat said *{message}* for 5.0 s.
                """
            ))

    def test_call_double_braces(self) -> None:
        t = template(f'{__package__}.res', 'template.md', double_braces=True)
        text = t(message='Meow!')
        self.assertEqual(
            text,
            dedent(
                """\
                # Cat

                The cat said *Meow!* for {len(message):.1f} s.
                """
            ))

class RouterTest(TestCase):
    def setUp(self) -> None:
        self.router: Router[str] = Router({
            '^/cats/([^/]+)$': self.query_cat,
            'cats': self.query_void
        })

    @staticmethod
    def query_cat(cat_id: str | None = None, *_: str | None) -> str:
        return f'Cat #{cat_id}'

    @staticmethod
    def query_void(*_: str | None) -> str:
        raise LookupError()

    def test_route(self) -> None:
        cat = self.router.route('/cats/frank')
        self.assertEqual(cat, 'Cat #frank')

    def test_route_no_result(self) -> None:
        with self.assertRaisesRegex(LookupError, 'foo'):
            self.router.route('foo')
