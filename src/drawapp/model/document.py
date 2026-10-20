"""The list of drawn items, with undo and redo."""

ADD = "add"
REMOVE = "remove"


class Document:
    def __init__(self):
        self.items = []
        self._undo = []  # (ADD | REMOVE, [(index, item), ...]) with ascending indices
        self._redo = []
        self._group = None
        self.listeners = []  # called with no arguments after every change

    # -- edits ---------------------------------------------------------
    def add(self, item):
        self.items.append(item)
        self._record((ADD, [(len(self.items) - 1, item)]))

    def erase(self, items):
        """Remove the given items. Inside a group, repeated calls undo as one step."""
        targets = [(i, it) for i, it in enumerate(self.items) if any(it is t for t in items)]
        if not targets:
            return
        self.items = [it for it in self.items if not any(it is t for _, t in targets)]
        if self._group is not None:
            self._group.append(targets)
            self._changed()
        else:
            self._record((REMOVE, targets))

    def clear(self):
        self.erase(list(self.items))

    def begin_group(self):
        self._group = []

    def end_group(self):
        removed, self._group = self._group, None
        if removed:
            # Indices were taken at different times; rebuild them against the
            # list as it was before the group so undo restores original order.
            self._record((REMOVE, self._original_indices(removed)))

    def items_at(self, x, y, radius):
        return [it for it in self.items if it.hit(x, y, radius)]

    # -- history -------------------------------------------------------
    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def undo(self):
        if not self._undo:
            return
        op = self._undo.pop()
        self._apply(op, reverse=True)
        self._redo.append(op)
        self._changed()

    def redo(self):
        if not self._redo:
            return
        op = self._redo.pop()
        self._apply(op, reverse=False)
        self._undo.append(op)
        self._changed()

    # -- internals -----------------------------------------------------
    def _record(self, op):
        self._undo.append(op)
        self._redo.clear()
        self._changed()

    def _apply(self, op, reverse):
        kind, entries = op
        inserting = (kind == ADD) != reverse
        if inserting:
            for index, item in entries:
                self.items.insert(index, item)
        else:
            self.items = [it for it in self.items if not any(it is e for _, e in entries)]

    def _original_indices(self, batches):
        """Turn indices recorded mid-group into indices in the pre-group list."""
        before = list(self.items)
        for batch in reversed(batches):
            for index, item in batch:
                before.insert(index, item)
        ids = {id(item) for batch in batches for _, item in batch}
        return [(i, it) for i, it in enumerate(before) if id(it) in ids]

    def _changed(self):
        for listener in self.listeners:
            listener()
