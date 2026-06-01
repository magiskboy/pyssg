"""Neutral filesystem events and pure coalescing.

This module is deliberately free of any third-party dependency and of any IO or
clock access: it defines the backend-neutral :class:`FsEvent` that the
incremental engine consumes and the pure :func:`coalesce` debounce
merge. Keeping it pure makes the merge rules exhaustively unit-testable and lets
the engine stay unaware that ``watchdog`` exists at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = ["FsEvent", "coalesce"]

EventKind = Literal["add", "modify", "delete", "move"]


@dataclass(frozen=True, slots=True)
class FsEvent:
    """A backend-neutral filesystem change.

    The incremental engine only ever sees :class:`FsEvent`; the concrete
    watcher backend (``watchdog``) is hidden behind ``pyssg/watch`` so the
    backend can be swapped without touching core.

    Attributes:
        kind: The change kind.
        path: For ``add``/``modify``/``delete`` the affected path; for ``move``
            the source path.
        dest: Only set for ``move``: the destination path. ``None`` otherwise.
    """

    kind: EventKind
    path: str
    dest: str | None = None


def coalesce(events: list[FsEvent]) -> list[FsEvent]:
    """Merge a burst of events into the minimal equivalent set.

    Within a single debounce window the same path may emit several raw events;
    collapsing them avoids redundant rebuild work. The function is pure: it has
    no IO and no clock, so it is fully deterministic and exhaustively testable.

    Merge rules (per path, by final net effect):

    - multiple ``modify`` -> a single ``modify``;
    - ``add`` then ``modify`` -> ``add`` (the file is still new, just edited);
    - ``modify`` then ``delete`` -> ``delete`` (the edit no longer matters);
    - ``add`` then ``delete`` -> dropped entirely (the file never settled);
    - ``delete`` then ``add`` -> ``modify`` (the file was replaced in place,
      documented here so the engine treats a delete+recreate the same as an
      editor's atomic save);
    - ``move`` events are preserved verbatim and never merged away, to keep the
      rename identity. A move's ``path`` (source) and ``dest``
      (destination) are independent keys, so a later edit on the destination is
      tracked separately from the move itself.

    Ordering: the result preserves the order in which each path *first* appears
    in ``events``. This gives a stable, deterministic batch for downstream
    seeding.

    Args:
        events: Raw events in arrival order.

    Returns:
        The coalesced events, order-preserving by first appearance. Paths whose
        net effect is "nothing happened" (``add`` then ``delete``) are omitted.
    """
    # Net kind accumulated per non-move path. ``None`` marks a path that has
    # been dropped (add+delete) but whose first-appearance slot we still hold so
    # ordering stays stable if it reappears.
    net: dict[str, EventKind | None] = {}
    # First-appearance order of keys (both non-move paths and move identities).
    order: list[str] = []
    # Move events kept verbatim, keyed by a synthetic identity so two distinct
    # moves never collapse into each other.
    moves: dict[str, FsEvent] = {}

    for event in events:
        if event.kind == "move":
            key = f"move\0{event.path}\0{event.dest}"
            if key not in moves:
                order.append(key)
            moves[key] = event
            continue

        path = event.path
        if path not in net:
            order.append(path)
            net[path] = event.kind
            continue

        net[path] = _merge_kind(net[path], event.kind)

    result: list[FsEvent] = []
    for key in order:
        move = moves.get(key)
        if move is not None:
            result.append(move)
            continue
        kind = net.get(key)
        if kind is None:
            # add+delete collapsed to nothing.
            continue
        result.append(FsEvent(kind, key))
    return result


def _merge_kind(prev: EventKind | None, curr: EventKind) -> EventKind | None:
    """Fold a new non-move event kind onto the accumulated kind for one path.

    ``prev is None`` means the path's net effect was previously cancelled out
    (add+delete); a subsequent event restarts accumulation from that kind.
    Returns the new net kind, or ``None`` when the net effect is "no change".
    """
    if prev is None:
        # Previously cancelled (add+delete); treat the next event fresh.
        return curr

    match (prev, curr):
        case (_, "modify") if prev in ("add", "modify"):
            # add+modify -> add ; modify+modify -> modify
            return prev
        case ("add", "delete"):
            # add+delete -> nothing.
            return None
        case (_, "delete"):
            # modify+delete (or delete+delete) -> delete
            return "delete"
        case ("delete", "add"):
            # delete+add -> file replaced in place -> modify.
            return "modify"
        case (_, "add"):
            # add after a live (non-deleted) path: stay add-like; an add on an
            # already-added/modified path keeps the stronger "new file" intent.
            return "add" if prev == "add" else prev
        case _:
            return curr
