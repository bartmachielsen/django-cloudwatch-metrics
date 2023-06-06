"""Make objects hashable."""
import base64
import hashlib


def make_hashable(o):
    """Make object of certain type hashable."""
    if isinstance(o, (tuple, list)):
        return tuple(make_hashable(e) for e in o)

    if isinstance(o, dict):
        return tuple(sorted((k, make_hashable(v)) for k, v in o.items()))

    if isinstance(o, (set, frozenset)):
        return tuple(sorted(make_hashable(e) for e in o))

    return o


def create_cache_key(*o):
    """Create Hash key from object."""
    hasher = hashlib.sha256()
    hasher.update(repr(make_hashable(o)).encode())
    return base64.b64encode(hasher.digest()).decode()
