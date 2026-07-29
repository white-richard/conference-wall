import pytest

from confwall.config import Config, VenueConfig


@pytest.fixture
def mock_config() -> Config:
    return Config(
        window_months=4,
        venues={
            "mlsys": VenueConfig(primary_focus="Machine Learning", aliases=("MLSys",)),
            "osdi": VenueConfig(primary_focus="Software Systems", aliases=("OSDI",)),
            "chi": VenueConfig(primary_focus="HCI", aliases=("CHI",)),
        },
        alias_map={"mlsys": "mlsys", "osdi": "osdi", "chi": "chi"},
    )
