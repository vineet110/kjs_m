"""Phone numbers (UI step 7, light check): digits, spaces, - ( ) and an optional leading +, 6 to 15 digits.
Empty is fine (the phone is optional). Every form that takes a phone uses the same check."""
from tests.conftest import HDR, login, make_user
from tests.test_content import PARTNER
from tests.test_public import LEAD

GOOD = ["+91 98765 43210", "+971 50-123-4567", "+44 (020) 7946 0958", "9876543210"]
BAD = ["call me", "+91 98765x43210", "12345", "+1 2345 6789 0123 4567"]


async def test_enquiry_phone_is_checked(client):
    for bad in BAD:
        assert (await client.post("/api/v1/public/leads", json=LEAD | {"phone": bad})).status_code == 422, bad
    for good in GOOD:
        assert (await client.post("/api/v1/public/leads", json=LEAD | {"phone": good})).status_code == 201, good


async def test_partner_phone_is_checked(client):
    assert (await client.post("/api/v1/public/partners", json=PARTNER | {"phone": "call me"}, headers=HDR)).status_code == 422
    assert (await client.post("/api/v1/public/partners", json=PARTNER | {"phone": "+971 50 123 4567"}, headers=HDR)).status_code == 201


async def test_signup_and_profile_phone_are_checked(client):
    body = {"name": "Esha K", "email": "esha@kjsindia.com", "password": "a-long-password-1"}
    assert (await client.post("/api/v1/auth/signup", json=body | {"phone": "12345"}, headers=HDR)).status_code == 422
    assert (await client.post("/api/v1/auth/signup", json=body | {"phone": "+91 98765 43210"}, headers=HDR)).status_code == 201
    await make_user("me@kjsindia.com", permissions=["leads.view"])
    await login(client, "me@kjsindia.com")
    assert (await client.patch("/api/v1/auth/profile", json={"phone": "not a phone"}, headers=HDR)).status_code == 422
    assert (await client.patch("/api/v1/auth/profile", json={"phone": "+91 90000 00000"}, headers=HDR)).status_code < 300
    assert (await client.patch("/api/v1/auth/profile", json={"phone": ""}, headers=HDR)).status_code < 300  # clearing it


async def test_phone_takes_only_plain_digits(client):
    # Arabic-Indic or full-width digits pass Python's \d but staff can't dial them (review)
    for odd in ["+٩١ ٩٨٧٦٥ ٤٣٢١٠", "９８７６５４３２１０"]:
        assert (await client.post("/api/v1/public/leads", json=LEAD | {"phone": odd})).status_code == 422, odd
