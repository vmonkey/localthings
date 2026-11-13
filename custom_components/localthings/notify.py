"""Notify platform for Local Things (TVs).

One notify entity per TV: a pop-up with a title, the message and an OK
button, through the TV's notification service (capabilities/tv.py's notify_body).
"""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LocalThingsCoordinator
from .entity import LocalThingsEntity, _is_included
from .registry.entities import NotifyDesc


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: LocalThingsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LocalThingsNotify(coordinator, b)
        for b in coordinator.bound
        if isinstance(b.desc, NotifyDesc) and _is_included(b, coordinator)
    )


class LocalThingsNotify(LocalThingsEntity, NotifyEntity):
    """Pop-up notifications on the TV."""

    _attr_supported_features = NotifyEntityFeature.TITLE

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        await self.coordinator.av.async_notify(title, message)
