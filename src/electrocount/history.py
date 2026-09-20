from copy import deepcopy


class History:
    """Bounded undo snapshots of domain data, never PDF bytes or render cache."""
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def record(self, project):
        self.undo_stack.append(deepcopy(project))
        self.undo_stack = self.undo_stack[-60:]
        self.redo_stack.clear()

    def undo(self, current):
        if not self.undo_stack:
            return current
        self.redo_stack.append(deepcopy(current))
        return self.undo_stack.pop()

    def redo(self, current):
        if not self.redo_stack:
            return current
        self.undo_stack.append(deepcopy(current))
        return self.redo_stack.pop()
