"""Portal areas switched on and off for phased releases (config/modules.ini).

Each area is `on` (everyone), `admin` (admins only, to try it on the live site first) or `off` (nobody).
Off hides an area; it never deletes data. Leads, tasks, My day, profile, approvals, users and settings
have no switch.

- Routes:  `dependencies=[Depends(require_module("order_boards"))]`  -> 404 `module_off` when hidden.
- Screens: `/auth/me` sends `modules` ({area: true/false}) already worked out for the person.
- Jobs:    `@job("board_alerts", module="order_boards")` is skipped only when the area is `off`.
- Links:   `area_of_link("/employee/order-boards/X")` -> "order_boards" (notifications, emails).
"""
import logging

from fastapi import Depends

from app.core.config.ini import ModulesIni, cfg
from app.core.deps import current_user
from app.core.errors import AppError
from app.models.user import User

log = logging.getLogger(__name__)
AREAS = tuple(ModulesIni.model_fields)

# Portal pages of each area (the start of the link). Used for notification and email links.
AREA_PAGES = {
    "batches": ("/employee/batches", "/admin/auto-assign"),
    "order_boards": ("/employee/order-boards", "/admin/order-boards"),
    "attendance": ("/employee/attendance", "/admin/team-attendance", "/admin/holidays"),
    "website_admin": ("/admin/products", "/admin/website", "/admin/koko"),
    "analytics": ("/admin/analytics",),
    "alerts": ("/admin/alerts",),
    "audit": ("/admin/audit",),
}
# Who owns a stored file -> its area (user photos have no area: always on)
AREA_OF_FILE_OWNER = {"board": "order_boards", "product": "website_admin"}


def level(area: str) -> str:
    return getattr(cfg().modules, area)


def visible(user: User, area: str | None) -> bool:
    """Can this person use the area? `None` = no area (always on)."""
    if area is None:
        return True
    lv = level(area)
    return lv == "on" or (lv == "admin" and user.role == "admin")


def visible_to(user: User) -> dict[str, bool]:
    return {a: visible(user, a) for a in AREAS}


def running(area: str) -> bool:
    """Background work of an area runs unless it is `off` (with `admin`, admins can test it fully)."""
    return level(area) != "off"


def area_of_link(link: str) -> str | None:
    for area, pages in AREA_PAGES.items():
        if any(link == p or link.startswith(p + "/") or link.startswith(p + "?") for p in pages):
            return area
    return None


def link_for(user: User, link: str) -> str:
    """The link if the person may open it, else "" (the text of the notification still shows)."""
    return link if link and visible(user, area_of_link(link)) else ""


def require_visible(user: User, area: str | None) -> None:
    """404 `module_off` when the area is hidden from this person (same answer as a missing page)."""
    if not visible(user, area):
        log.info("module.hidden", extra={"area": area})  # not "module": Python's log records use that name
        raise AppError(404, "module_off", "This part of the portal isn't available yet.", {"module": area})


def require_module(area: str):
    """Route dependency: 404 `module_off` when the area is hidden from this person."""
    if area not in AREAS:
        raise ValueError(f"unknown area {area!r}")  # a typo in the code fails at start-up, not later

    async def checker(user: User = Depends(current_user)) -> User:
        require_visible(user, area)
        return user

    checker.module = area  # read by the route map test
    return checker


def area(name: str) -> list:
    """For `dependencies=` on a route or a whole router: it belongs to this portal area."""
    return [Depends(require_module(name))]
