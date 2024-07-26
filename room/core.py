"""Core concepts.

.. data:: Text

   String with visible characters.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class Player(BaseModel): # type: ignore[misc]
    """Player of the game.

    .. attribute: id

       Unique player ID.

    .. attribute:: name

       Name or nick name.
    """

    id: str
    name: Text

    @model_validator(mode='before')
    @classmethod
    def _check(cls, data: dict[str, object]) -> dict[str, object]:
        # Update name
        if 'name' not in data:
            data['name'] = 'Guest'
        return data

class PrivatePlayer(Player): # type: ignore[misc]
    """Private view of the player.

    .. attribute:: token

       Authentication token.

    .. attribute:: tutorial

       Indicates if the player has completed the tutorial.
    """

    token: str
    tutorial: bool

    @model_validator(mode='before')
    @classmethod
    def _check(cls, data: dict[str, object]) -> dict[str, object]:
        data = super()._check(data) # type: ignore[operator]
        # Update tutorial
        if 'tutorial' not in data:
            data['tutorial'] = False
        return data

    def update(self, patch: PrivatePlayer) -> None:
        """Update the player with a *patch*.

        :attr:`id` and :attr:`token` are immutable and ignored.
        """
        self.name = patch.name
        self.tutorial = patch.tutorial
