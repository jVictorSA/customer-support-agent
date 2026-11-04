"""Central metadata module used by Alembic.

Import the ORM models from each module here so ``Base.metadata`` contains every
table when Alembic runs ``--autogenerate``.
"""

from customer_support_agent.db.base import Base

__all__ = ["Base"]
