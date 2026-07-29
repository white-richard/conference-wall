import os

import pytest

from confwall.conference_source import CCFConferenceSource
from confwall.config import load_config
from confwall.http_client import HttpClient
from confwall.photos import PEXELS_SEARCH_URL


@pytest.mark.live
def test_live_ccf_snapshot_download():
    client = HttpClient()
    source = CCFConferenceSource(http_client=client)
    config = load_config("config.yml")

    editions, count = source.load_editions(config)
    assert count > 0
    assert len(editions) > 0


@pytest.mark.live
def test_live_pexels_search():
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        pytest.skip("PEXELS_API_KEY not set")

    client = HttpClient()
    headers = {"Authorization": api_key}
    params = {"query": "Austin Texas USA skyline", "orientation": "landscape", "per_page": 5}
    res = client.get_json(PEXELS_SEARCH_URL, headers=headers, params=params)
    assert isinstance(res, dict)
    assert "photos" in res
    assert len(res["photos"]) > 0
