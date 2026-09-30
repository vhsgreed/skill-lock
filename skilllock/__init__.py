"""skilllock — hash pinning and per-skill update control for agent skill bundles."""
from .core import LockError, SkillStatus, lock_root, update_skill, verify

__all__ = ["LockError", "SkillStatus", "lock_root", "verify", "update_skill"]
__version__ = "0.1.0"
