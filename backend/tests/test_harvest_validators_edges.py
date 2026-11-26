"""R57.ii edge cases: the shared address / setting-name rules on create AND edit."""
import pytest
from pydantic import ValidationError

from app.schemas.harvest import HarvestSourceIn, HarvestSourceUpdate

BASE = {"name": "Feed", "source_type": "rss", "url": "https://example.com/feed"}


def test_edit_without_url_or_env_name_is_fine():
    u = HarvestSourceUpdate(name="New name")
    assert u.url is None and u.auth_env_var is None
    assert HarvestSourceUpdate(url=None, auth_env_var=None).model_fields_set == {"url", "auth_env_var"}


@pytest.mark.parametrize("model", [HarvestSourceIn, HarvestSourceUpdate])
def test_lengths_still_apply_with_the_shared_rules(model):
    with pytest.raises(ValidationError):
        model(**{**BASE, "url": "https://example.com/" + "a" * 500})
    with pytest.raises(ValidationError):
        model(**{**BASE, "url": "http"})


@pytest.mark.parametrize("model", [HarvestSourceIn, HarvestSourceUpdate])
@pytest.mark.parametrize("url", ["https://[::1]/x", "https://localhost./x", "https://intranet/x",
                                 "https://[::ffff:10.0.0.1]/x", "https://user:pw@example.com/x", "ftp://example.com/x"])
def test_internal_or_odd_addresses_are_refused_on_create_and_edit(model, url):
    with pytest.raises(ValidationError):
        model(**{**BASE, "url": url})


@pytest.mark.parametrize("model", [HarvestSourceIn, HarvestSourceUpdate])
def test_a_public_ipv6_with_a_port_is_allowed_on_create_and_edit(model):
    assert model(**{**BASE, "url": "https://[2606:4700:4700::1111]:8443/feed"}).url.startswith("https://[2606")


@pytest.mark.parametrize("model", [HarvestSourceIn, HarvestSourceUpdate])
def test_only_harvest_setting_names(model):
    with pytest.raises(ValidationError):
        model(**{**BASE, "auth_env_var": "SECRET_KEY"})
    assert model(**{**BASE, "auth_env_var": ""}).auth_env_var == ""
