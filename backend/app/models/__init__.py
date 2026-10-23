# Import every model here so Alembic autogenerate can see all tables.
from app.models.audit import AuditLog  # noqa: F401
from app.models.calendar import Holiday  # noqa: F401
from app.models.catalog import Category, Product  # noqa: F401
from app.models.lead import Lead  # noqa: F401
from app.models.order_board import OrderBoard  # noqa: F401
from app.models.user import AvailabilityLog, User, UserSession  # noqa: F401
