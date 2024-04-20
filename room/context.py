"""Context-Local state.

.. data:: game

   Current game.

.. data:: player

   Current player.

.. data:: room

   Current room.
"""

from __future__ import annotations

from contextvars import ContextVar
import typing

if typing.TYPE_CHECKING:
    from .core import PrivatePlayer
    from .game import Game, OnlineRoom

game: ContextVar[Game] = ContextVar('game')
player: ContextVar[PrivatePlayer] = ContextVar('player')
room: ContextVar[OnlineRoom] = ContextVar('room')
