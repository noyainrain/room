"""Core concepts."""

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel

class Player(BaseModel): # type: ignore[misc]
    """Player of the game.

    .. attribute: id

       Unique player ID.
    """

    id: str

class PrivatePlayer(Player): # type: ignore[misc]
    """Private view of the player.

    .. attribute:: token

       Authentication token.
    """

    token: str

def parse_room_url(url: str) -> tuple[str, str, str]:
    """TODO.

    `(prefix, room_id, fragment)`.
    """
    components = urlsplit(url)
    path = Path(components.path)
    print('PATH', path.parts, len(path.parts))
    try:
        _, prefix, room_id = path.parts
    except TypeError:
        raise ValueError(f'Bad url {url}') from None
    print('PATH', _, prefix, room_id)
    if prefix != 'invites':
        raise ValueError(f'Bad url {url}')
    return (prefix, room_id, components.fragment)
