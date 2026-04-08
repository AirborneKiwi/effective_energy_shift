from __future__ import annotations

from dataclasses import dataclass
from modulefinder import Module
from typing import Callable, Dict, List

# Import and register all decorators
import decorator_registry as dec_reg

@dataclass
class DebugGroup:
    name: str
    import_func: Callable[[], Module]
    module = None

    def bootstrap(self):
        print(f'---- BOOTSTRAPPING {self.name} ----')
        self.module = self.import_func()
        assert hasattr(self.module, 'targets')
        assert hasattr(self.module, 'ENABLED')
        try:
            assert hasattr(self.module, 'decorator_group')
        except AssertionError:
            setattr(self.module, 'decorator_group', 'default')

        self.apply()

    def apply(self):
        self.set_enabled(True)  # they will be applied, if apply is called
        print(f'Applying decorators to {self.module.targets} ----')
        dec_reg.apply_decorators(*(self.module.targets))

    def set_enabled(self, enabled: bool):
        if enabled:
            dec_reg.enable_group(self.module.decorator_group)
        else:
            dec_reg.disable_group(self.module.decorator_group)
        self.module.ENABLED = enabled


_debug_groups: Dict[str, DebugGroup] = {}

def get_bootstrap_option() -> List[str]:
    return list(_debug_groups.keys())

def bootstrap(name: str) -> DebugGroup:
    _debug_groups[name].bootstrap()
    return _debug_groups[name]


def set_enabled_debug_groups(enabled:bool, group_names: List[str] = None) -> None:
    # Import modules so registration side effects happen.
    if group_names is None:
        for name, debug_group in _debug_groups.items():
            debug_group.set_enabled(enabled)
        return

    for name in group_names:
        _debug_groups[name].set_enabled(enabled)

def enable_debug_groups(group_names: List[str] = None):
    return set_enabled_debug_groups(True, group_names)

def disable_debug_groups(group_names: List[str] = None):
    return set_enabled_debug_groups(False, group_names)

# ------- SPECIFIC OPTIONS ------- #

def _import_test():
    import mefes.debug.test_decorators as test_decorators
    return test_decorators

_debug_groups['test'] = DebugGroup('test', _import_test)


def _import_event_recording():
    import mefes.debug.event_decorators as event_decorators
    return event_decorators

_debug_groups['event_recording'] = DebugGroup('event_recording', _import_event_recording)


def _import_tex_output():
    import mefes.debug.tex_decorators as tex_decorators
    return tex_decorators

_debug_groups['tex_output'] = DebugGroup('tex_output', _import_tex_output)



