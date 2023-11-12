"""Context-Local state.

.. data:: game

   Current game.

.. data:: room

   Current room.
"""

from __future__ import annotations

from contextvars import ContextVar
import typing

if typing.TYPE_CHECKING:
    from .game import Game, OnlineRoom

game: ContextVar[Game] = ContextVar('game')
room: ContextVar[OnlineRoom] = ContextVar('room')
