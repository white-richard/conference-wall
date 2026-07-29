from confwall.config import LocationOverride
from confwall.locations import parse_location


def test_parse_location_city_country():
    loc = parse_location("Vienna, Austria")
    assert loc.city == "Vienna"
    assert loc.country == "Austria"
    assert loc.region is None
    assert loc.location_key == "vienna|austria"
    assert loc.is_photographic is True


def test_parse_location_single_component():
    loc = parse_location("Singapore")
    assert loc.city == "Singapore"
    assert loc.country == "Singapore"
    assert loc.location_key == "singapore|singapore"
    assert loc.is_photographic is True


def test_parse_location_city_state_country():
    loc = parse_location("Las Vegas, NV, USA")
    assert loc.city == "Las Vegas"
    assert loc.country == "USA"
    assert loc.region == "NV"
    assert loc.location_key == "las vegas|usa"
    assert loc.is_photographic is True


def test_parse_location_non_us_region():
    loc = parse_location("Vancouver, BC, Canada")
    assert loc.city == "Vancouver"
    assert loc.country == "Canada"
    assert loc.region == "BC"
    assert loc.location_key == "vancouver|canada"
    assert loc.is_photographic is True


def test_parse_location_extra_whitespace():
    loc = parse_location("   Austin  ,   TX   ,   USA   ")
    assert loc.city == "Austin"
    assert loc.country == "USA"
    assert loc.region == "TX"
    assert loc.location_key == "austin|usa"


def test_parse_location_virtual_and_tbd():
    loc_tbd = parse_location("TBD")
    assert loc_tbd.is_photographic is False
    assert loc_tbd.location_key is None

    loc_virt = parse_location("Virtual / Online")
    assert loc_virt.is_photographic is False
    assert loc_virt.location_key is None

    loc_none = parse_location(None)
    assert loc_none.is_photographic is False


def test_parse_location_explicit_override():
    overrides = {
        "Unusual Place Name": LocationOverride(
            city="Correct City", country="Correct Country", display="Correct City, Correct Country"
        )
    }
    loc = parse_location("Unusual Place Name", overrides=overrides)
    assert loc.city == "Correct City"
    assert loc.country == "Correct Country"
    assert loc.display_place == "Correct City, Correct Country"
    assert loc.location_key == "correct city|correct country"
    assert loc.is_photographic is True
