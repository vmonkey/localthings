"""Samsung TV registry (oic.d.tv, #755).

The Smart Monitor's Tizen surface (by_type/monitor.py) plus what a TV adds:
the media player, remote, channel, apps and casting. Read per href like the
soundbar.
"""

from ..capabilities import av, common, tv
from ._base import DeviceRegistry, _build, unpolled

_OWN = [
    av.NETWORK,
    *tv.TV_MEDIA_SURFACE,
    tv.PICTURE_MODE,
    tv.CHANNEL,
    tv.CONTENT_INFO,
    tv.FIRMWARE_COVERAGE,
    tv.MEDIA_PLAYER,
    tv.CAST_SESSION,
    tv.CAST_ITEM,
    tv.THUMBNAIL,
    tv.REMOTE,
    tv.OPEN_APP,
    # PROBE_HREFS are read on every appliance (issue #301).
    common.FILE_LIST,
    common.FILE_TRANSFER,
]
_OWN_HREFS = {cap.href for cap in _OWN}


def _not_own(*groups):
    return [cap for group in groups for cap in group if cap.href not in _OWN_HREFS]


REGISTRY = DeviceRegistry(
    name="tv",
    capabilities=_build(
        [
            *unpolled(_not_own(av.IGNORED, tv.COVERAGE, tv.TV_COVERAGE, av.MEDIA_RESOURCES)),
            *_OWN,
        ]
    ),
    pattern_capabilities=[tv.APPDATA],
    # No OBSERVE and a short settle window, same as the soundbar.
    subscribe_tiers=(),
    write_settle_s=6.0,
    # In network standby the TV wakes every few minutes and answers most
    # reads, but not its power switch or remote.
    awake_href=tv.HREF_SWITCH,
)
