"""Various utilities."""

from __future__ import annotations

from asyncio import CancelledError, Task
from base64 import b64decode
from collections.abc import Callable, Generator
from contextlib import contextmanager
from io import BytesIO
import json
import random
from string import ascii_lowercase
from time import perf_counter
from typing import NamedTuple

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

class WSMessage(NamedTuple):
    """Websocket message type annotations."""

    # pylint: disable=missing-docstring,unused-argument

    type: WSMsgType
    data: str | bytes | WSCloseCode
    extra: str

    def json(self, *,
             loads: Callable[[str | bytes | bytearray], object] = json.loads) -> object: ...
