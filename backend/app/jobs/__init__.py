"""Background jobs. Import each job module here so it registers itself."""
from app.services import (  # noqa: F401,E402
    assign_service, board_service, file_service, lead_service, notification_service,
)
