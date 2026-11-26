from sqlalchemy import JSON, DateTime
from sqlalchemy.dialects.postgresql import JSONB

JSONBType = JSON().with_variant(JSONB(), "postgresql")
UtcDateTime = DateTime(timezone=True)

