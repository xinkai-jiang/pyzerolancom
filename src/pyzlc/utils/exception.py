class PyzlcErrorBase(Exception):
    """Base exception for all PyZLC errors."""

    pass


class NodeAlreadyInitializedError(PyzlcErrorBase):
    """Raised when trying to initialize a node that is already active."""

    pass


class ServiceTimeoutError(PyzlcErrorBase, TimeoutError):
    """Raised when a service discovery times out."""

    pass


# TODO: Add more specific exceptions as needed and use them in the codebase.
