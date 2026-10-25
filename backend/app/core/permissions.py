"""Permission keys (backlog D5).

Routes check a *permission*, never a role name. A role is only a default bundle:
- admin    -> every permission
- employee -> EMPLOYEE_DEFAULTS, plus any extras the admin ticks for that person
Adding a new permission = add a line here + use require_permission("...") on the route.
"""

PERMISSIONS: dict[str, str] = {
    "leads.view": "See and work on website / Koko leads",
    "leads.view_all": "See leads assigned to anyone (not only own)",
    "catalog.edit": "Add and edit products",
    "staff.approve": "Approve new staff and set their permissions",
    "audit.view": "See the audit log",
    "calendar.edit": "Manage the holiday calendar",
    "attendance.manage": "See team attendance and approve regularizations",
    "boards.manage": "Create and run order boards",
    "assign.manage": "Set up and run auto-assign",
    "content.edit": "Edit website text, offers and Koko knowledge",
    "tasks.assign": "Give tasks to other staff and see everyone's tasks",
    "files.approve": "Approve requests to delete files",
}

EMPLOYEE_DEFAULTS: list[str] = ["leads.view"]


def effective_permissions(role: str, extra: list[str] | None) -> set[str]:
    if role == "admin":
        return set(PERMISSIONS)
    return set(EMPLOYEE_DEFAULTS) | {p for p in (extra or []) if p in PERMISSIONS}
