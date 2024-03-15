"""Various utilities."""

from __future__ import annotations

from asyncio import CancelledError, Task
from base64 import b64decode
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import cache
from importlib import resources
from io import BytesIO
import json
import random
import re
from re import Match
from string import ascii_lowercase
from textwrap import dedent
from time import perf_counter
from typing import NamedTuple, Protocol, cast

from aiohttp import WSCloseCode, WSMsgType
from PIL import UnidentifiedImageError
import PIL.Image
from PIL.Image import Image

def randstr(length: int = 16, *, charset: str = ascii_lowercase) -> str:
    """Generate a random string with the given *length*.

    The result is comprised of characters from *charset*.
    """
    return ''.join(random.choice(charset) for _ in range(length))

@contextmanager
def timer() -> Generator[Callable[[], float], None, None]:
    """Context manager to time the execution of a block.

    The timer can be called to return the execution time in s.
    """
    def t() -> float:
        return end - start
    start = end = perf_counter()
    yield t
    end = perf_counter()

async def cancel(task: Task[object]) -> None:
    """Cancel the *task*."""
    task.cancel()
    try:
        await task
    except CancelledError:
        pass

def open_image_data_url(url: str) -> Image:
    """Open the given image data *url*."""
    prefix = 'data:image/png;base64,'
    if not url.startswith(prefix):
        raise ValueError(f'Bad url {url}')
    try:
        data = b64decode(url[len(prefix):], validate=True)
        return PIL.Image.open(BytesIO(data), formats=['png'])
    except (ValueError, UnidentifiedImageError) as e:
        raise ValueError(f'Bad url data {url}') from e

class Template(Protocol):
    """Render the f-string template with the given *kwargs*.

    f-string expression errors are passed through.
    """

    def __call__(self, **kwargs: object) -> str: ...

@cache # type: ignore[misc]
def template(package: str, resource: str, *, double_braces: bool = False) -> Template:
    """Load an f-string template from *resource* within *package*.

    The loaded template is cached. The template may not contain triple quotes.

    If *double_braces* preprocessing is enabled, double curly braces are used as delimiter, while
    any other curly braces are escaped.

    If there is a problem importing *package*, an :exc:`ImportError` is raised. If there is a
    problem reading *resource*, an :exc:`OSError` is raised. If there is a problem parsing the
    template, a :exc:`SyntaxError` is raised.
    """
    try:
        path = resources.files(package)
    except TypeError as e:
        raise ImportError('Relative package') from e
    text = (path / resource).read_text()
    if '"""' in text:
        raise SyntaxError('Unexpected """')

    if double_braces:
        def process(match: Match[str]) -> str:
            return braces[0] if len(braces := match[0]) == 2 else braces * 2
        text = re.sub(r'\{+|\}+', process, text)

    # pylint: disable=exec-used
    g: dict[str, object] = {}
    exec(
        dedent(
            '''\
            def t(**kwargs):
                globals().update(kwargs)
                return fr"""{}"""
            '''
        ).format(text),
        g)
    return cast(Template, g['t'])

class WSMessage(NamedTuple):
    """Websocket message type annotations."""

    # pylint: disable=missing-docstring,unused-argument

    type: WSMsgType
    data: str | bytes | WSCloseCode
    extra: str

    def json(self, *,
             loads: Callable[[str | bytes | bytearray], object] = json.loads) -> object: ...
