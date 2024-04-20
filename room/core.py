"""Core concepts."""

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
