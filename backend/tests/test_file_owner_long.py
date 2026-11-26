"""CR19: a product with a long name (slug over 60 characters) can get a file."""
from tests.conftest import HDR, login, make_user


async def test_a_long_product_name_can_get_a_photo(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    name = "Premium Instant Coffee Stick Pack Private Label Export Grade 2g Extra"
    p = (await client.post("/api/v1/admin/products", json={"category_slug": "coffee", "name": name}, headers=HDR)).json()
    assert len(p["slug"]) > 60
    r = await client.post("/api/v1/files", data={"owner_type": "product", "owner_id": p["slug"]},
                          files={"file": ("spec.pdf", b"%PDF-1.4 %%EOF", "application/pdf")}, headers=HDR)
    assert r.status_code == 201
