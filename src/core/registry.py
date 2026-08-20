# src/core/registry.py
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple
from src.domains.platform import Platform
from src.domains.action_type import ActionType
from src.interfaces.i_platform_handler import IPlatformHandler
from src.interfaces.i_action_handler import IActionHandler

@dataclass(frozen=True)
class PlatformBundle:
    platform_handler: IPlatformHandler
    action_handlers: Tuple[IActionHandler, ...]


class Registry:
    """An explicit handler catalog that can be safely isolated in tests/processes."""

    def __init__(self) -> None:
        self._platforms: Dict[Platform, IPlatformHandler] = {}
        self._actions: Dict[Tuple[Platform, ActionType], IActionHandler] = {}

    def register_platform(self, handler: IPlatformHandler) -> None:
        if handler.platform in self._platforms:
            raise ValueError(f"Platform already registered: {handler.platform.value}")
        self._platforms[handler.platform] = handler
        print(f"[Registry] Registered Platform: {handler.platform.value}")

    def register_action(self, handler: IActionHandler) -> None:
        key = (handler.platform, handler.action_type)
        if key in self._actions:
            raise ValueError(
                f"Action already registered: {handler.platform.value}/{handler.action_type.value}"
            )
        if handler.platform not in self._platforms:
            raise ValueError(f"Register platform before its actions: {handler.platform.value}")
        self._actions[key] = handler
        print(f"[Registry] Registered Action: {handler.platform.value} / {handler.action_type.value}")

    def register_bundle(self, bundle: PlatformBundle) -> None:
        platform = bundle.platform_handler.platform
        invalid = [handler for handler in bundle.action_handlers if handler.platform != platform]
        if invalid:
            raise ValueError(f"Bundle contains an action for a different platform: {platform.value}")
        self.register_platform(bundle.platform_handler)
        for handler in bundle.action_handlers:
            self.register_action(handler)

    def get_platform(self, platform: Platform):
        return self._platforms.get(platform)

    def get_action(self, platform: Platform, action: ActionType):
        return self._actions.get((platform, action))

    def supports(self, platform: Platform, action: ActionType) -> bool:
        return platform in self._platforms and (platform, action) in self._actions

    @property
    def platforms(self) -> Iterable[Platform]:
        return tuple(self._platforms)
