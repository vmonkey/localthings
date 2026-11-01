"""Lost replies and optimistic modes must not invent playback evidence."""

from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.localthings.coordinator import LocalThingsCoordinator
from custom_components.localthings.media_player import _PROFILES, LocalThingsMediaPlayer
from custom_components.localthings.registry.capabilities import soundbar
from custom_components.localthings.registry.discovery import BoundEntity
from tests.localthings.test_soundbar import ENTRY_DATA, FakeSoundbarSession


@pytest.fixture
def playback(hass, monkeypatch):
    coordinator = LocalThingsCoordinator(
        hass, MockConfigEntry(domain="localthings", data=ENTRY_DATA)
    )
    profile = _PROFILES["soundbar"]
    capability = soundbar.MEDIA_PLAYER
    bound = BoundEntity(
        href=profile.playback_href, capability=capability, desc=capability.entities[0]
    )
    player = LocalThingsMediaPlayer(coordinator, bound, profile)
    monkeypatch.setattr(coordinator, "async_request_refresh", AsyncMock())
    coordinator._write_settle_s = 0
    for href, rep in (
        (profile.power_href, {"value": True}),
        (profile.track_hrefs[0], {"title": "Track"}),
        (profile.playback_href, {"position": 120_000, "modes": ["pause"]}),
    ):
        coordinator._observe.apply(href, rep, source="poll")
    return player, coordinator, profile


async def test_lost_seek_reply_does_not_apply_delta_twice(playback, monkeypatch):
    player, coordinator, _ = playback
    session = FakeSoundbarSession()
    device_position = 120
    writes = []

    def write(path, body, timeout=None):
        nonlocal device_position
        device_position += body["position"]
        writes.append(body.copy())
        raise TimeoutError("device applied seek, but response was lost")

    monkeypatch.setattr(session, "write", write)
    coordinator._session = session
    reconnect = Mock()
    monkeypatch.setattr(coordinator, "_connect_session", reconnect)
    evidence = player._position_updated_at, player._last_position_evidence

    with pytest.raises(HomeAssistantError) as err:
        await player.async_media_seek(180)

    assert err.value.translation_key == "command_failed"
    assert writes == [{"modes": ["seek"], "position": 60}]
    assert device_position == 180
    assert coordinator._session is None
    reconnect.assert_not_called()
    assert player.media_position == 120  # no fabricated confirmation
    assert (player._position_updated_at, player._last_position_evidence) == evidence


@pytest.mark.parametrize(
    "command", ["async_media_play_pause", "async_media_next_track", "async_media_previous_track"]
)
async def test_relative_commands_are_not_repeated_after_a_lost_reply(
    playback, monkeypatch, command
):
    player, coordinator, _ = playback
    session = FakeSoundbarSession()
    write = Mock(side_effect=TimeoutError("reply lost"))
    monkeypatch.setattr(session, "write", write)
    coordinator._session = session
    reconnect = Mock()
    monkeypatch.setattr(coordinator, "_connect_session", reconnect)

    with pytest.raises(HomeAssistantError):
        await getattr(player, command)()

    write.assert_called_once()
    reconnect.assert_not_called()


async def test_absolute_volume_still_retries_after_reconnect(playback, monkeypatch):
    player, coordinator, _ = playback
    session = FakeSoundbarSession()
    write = Mock(side_effect=[TimeoutError("reply lost"), (0x44, None)])
    monkeypatch.setattr(session, "write", write)
    coordinator._session = session

    def reconnect():
        coordinator._session = session

    monkeypatch.setattr(coordinator, "_connect_session", reconnect)
    coordinator._RECONNECT_PAUSE_S = 0
    await player.async_set_volume_level(0.42)
    assert [call.args[1] for call in write.call_args_list] == [{"volume": 42}, {"volume": 42}]


@pytest.mark.parametrize(
    "command", ["async_media_play_pause", "async_media_play", "async_media_pause"]
)
async def test_playback_commands_wait_for_fresh_position_on_a_stopped_feed(
    playback, monkeypatch, command
):
    player, coordinator, profile = playback
    coordinator._observe.apply(profile.playback_href, {"modes": ["stop"]}, source="poll")
    coordinator._observe.apply(
        "/sec/networkaudio/playback",
        {"x.com.samsung.networkaudio.status": "PLAYING"},
        source="poll",
    )
    put = AsyncMock()
    monkeypatch.setattr(coordinator, "_async_put", put)
    assert not player.supported_features & MediaPlayerEntityFeature.SEEK

    await getattr(player, command)()

    assert not player.supported_features & MediaPlayerEntityFeature.SEEK
    assert player.media_position is None
    await player.async_media_seek(180)
    assert put.await_count == 1  # the playback command only

    coordinator._observe.apply(
        profile.playback_href, {"modes": ["play"], "position": 130_000}, source="poll"
    )
    assert player.supported_features & MediaPlayerEntityFeature.SEEK
    assert player.media_position == 130


@pytest.mark.parametrize(
    "command", ["async_media_play_pause", "async_media_play", "async_media_pause"]
)
async def test_playback_commands_preserve_a_usable_position(playback, monkeypatch, command):
    player, coordinator, _ = playback
    monkeypatch.setattr(coordinator, "_async_put", AsyncMock())
    await getattr(player, command)()
    assert player.supported_features & MediaPlayerEntityFeature.SEEK
    assert player.media_position == 120
