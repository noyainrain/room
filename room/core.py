"""TODO."""

from pydantic import BaseModel

# TODO do we need this for this feature, do we expose this somewhere, e.g. in Member?
class Player(BaseModel): # type: ignore[misc]
    """TODO.

    .. attribute: id

       TODO.
    """

    id: str

# Storage: players/{id}.json
class PrivatePlayer(Player): # type: ignore[misc]
    """TODO.

    .. attribute:: token

       TODO.
    """

    token: str
