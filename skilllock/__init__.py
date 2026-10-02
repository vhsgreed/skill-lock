"""skilllock — hash pinning and per-skill update control for agent skill bundles."""
from .core import LockError, SkillStatus, lock_root, resolve_update_source, save_lock, update_skill, verify

__all__ = ["LockError", "SkillStatus", "lock_root", "verify", "update_skill", "save_lock", "resolve_update_source"]
__version__ = "0.2.0"
