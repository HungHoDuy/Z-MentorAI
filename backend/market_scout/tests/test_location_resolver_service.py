from backend.market_scout.services.trend_tracker.location_resolver_service import LocationResolverService


def test_location_taxonomy_contains_legacy_63_vietnam_locations() -> None:
    resolver = LocationResolverService()

    assert len(resolver.locations) == 63


def test_resolves_common_city_aliases() -> None:
    resolver = LocationResolverService()

    assert resolver.resolve("viec lam tai HCM").location_id == "ho-chi-minh"
    assert resolver.resolve("nhu cau tuyen dung o Sai Gon").location_id == "ho-chi-minh"
    assert resolver.resolve("backend engineer tai HN").location_id == "ha-noi"
    assert resolver.resolve("nhan vien kinh doanh tai TP Ho Chi Minh").location_id == "ho-chi-minh"


def test_resolves_less_common_provinces() -> None:
    resolver = LocationResolverService()

    assert resolver.resolve("viec lam tai Ba Ria Vung Tau").location_id == "ba-ria-vung-tau"
    assert resolver.resolve("nhu cau tuyen dung tai Dak Lak").location_id == "dak-lak"
    assert resolver.resolve("nhu cau tuyen dung tai Thua Thien Hue").location_id == "thua-thien-hue"
    assert resolver.resolve("viec lam tai Ca Mau").location_id == "ca-mau"
