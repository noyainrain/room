"""Tile effects and causes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .core import Text

class Cause(BaseModel): # type: ignore[misc]
    """Cause of a tile effect.

    .. attribute:: type

       Type of the cause.
    """

    type: str

    def __hash__(self) -> int:
        return hash(self.type)

class Effect(BaseModel): # type: ignore[misc]
    """Tile effect.

    .. attribute:: type

       Type of the effect.
    """

    type: str

    async def apply(self, tile_index: int) -> Effect:
        """Apply the effect to the tile at *tile_index*.

        The applied effect with concrete result details is returned.
        """
        raise NotImplementedError()

class OpenDialogEffect(Effect): # type: ignore[misc]
    """Effect of opening a dialog, i.e. a text message to be acknowledged.

    .. attribute:: message

       Dialog message. Paragraphs are presented one after the other.
    """

    type: Literal['OpenDialogEffect'] = 'OpenDialogEffect'
    message: Text

    async def apply(self, tile_index: int) -> OpenDialogEffect:
        return self
