"""reStructuredText-style IO helpers."""

from __future__ import annotations


class Reader:
    """Read records from a source.

    :param source: Where to read from.
    :type source: str
    """

    def read(self, count: int) -> list[str]:
        """Read ``count`` records.

        :param count: How many records to read.
        :returns: The records read.
        :rtype: list
        :raises IOError: If the source is unavailable.
        """
        raise NotImplementedError

    async def aclose(self) -> None:
        """Close the reader asynchronously."""
        raise NotImplementedError
