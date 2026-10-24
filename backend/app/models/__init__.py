# Import every model here so Alembic autogenerate can see all tables.
from app.models.audit import AuditLog  # noqa: F401
from app.models.calendar import Holiday  # noqa: F401
from app.models.catalog import Category, Product  # noqa: F401
from app.models.lead import Lead, LeadNote  # noqa: F401
from app.models.order_board import BoardMember, BoardStep, OrderBoard  # noqa: F401
from app.models.user import AvailabilityLog, User, UserSession  # noqa: F401
from app.models.attendance import Attendance, Regularization  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.task import Task  # noqa: F401
from app.models.file import StoredFile  # noqa: F401
from app.models.batch import Batch, BuyerRecord, RecordList  # noqa: F401
from app.models.content import KokoChat, Offer, PartnerApplication, SiteText  # noqa: F401
