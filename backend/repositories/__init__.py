"""
Stage60 DB Governance - Repositories package.

Thin data access layer. Services should use these instead of direct get_connection()
or raw SQL in most cases.

See docs/governance/stage60-db-governance-plan.md and 
docs/agent-md/worker/stage-60d-db-access-inventory-report.md
"""

from .job_repository import JobRepository
from .voice_model_repository import VoiceModelRepository

__all__ = ["JobRepository", "VoiceModelRepository"]
