"""Core concepts.

.. data:: Text

   String with visible characters.
"""

from typing import Annotated

from pydantic import BaseModel, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

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
