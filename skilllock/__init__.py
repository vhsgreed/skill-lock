"""skilllock — hash pinning and per-skill update control for agent skill bundles."""
from .core import LockError, SkillStatus, lock_root, save_lock, update_skill, verify

__all__ = ["LockError", "SkillStatus", "lock_root", "verify", "update_skill", "save_lock"]
__version__ = "0.2.0"
