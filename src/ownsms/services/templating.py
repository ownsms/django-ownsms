import re

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def render(text, variables):
    """Returns (rendered, missing_keys). missing_keys non-empty -> do not use rendered."""
    vars_ = variables or {}
    missing = [m.group(1) for m in _PLACEHOLDER.finditer(text) if m.group(1) not in vars_]
    if missing:
        return None, missing
    return _PLACEHOLDER.sub(lambda m: str(vars_[m.group(1)]), text), []
