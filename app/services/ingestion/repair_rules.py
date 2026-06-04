from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identidade import RepairRule


def create_or_update_repair_rule(
    db: Session,
    *,
    rule_type: str,
    match_payload: dict[str, Any],
    action_payload: dict[str, Any],
    enabled: bool = True,
    reason: str | None = None,
    created_by: str | None = None,
) -> RepairRule:
    existing = db.scalar(
        select(RepairRule).where(
            RepairRule.rule_type == rule_type,
            RepairRule.match_payload == match_payload,
        )
    )
    if existing is None:
        existing = RepairRule(
            rule_type=rule_type,
            enabled=enabled,
            match_payload=match_payload,
            action_payload=action_payload,
            reason=reason,
            created_by=created_by,
        )
        db.add(existing)
        db.flush()
        return existing

    existing.enabled = enabled
    existing.action_payload = action_payload
    existing.reason = reason
    existing.created_by = created_by
    db.flush()
    return existing


def list_enabled_repair_rules(db: Session, *, rule_type: str | None = None) -> list[RepairRule]:
    query = select(RepairRule).where(RepairRule.enabled.is_(True))
    if rule_type is not None:
        query = query.where(RepairRule.rule_type == rule_type)
    return list(db.execute(query.order_by(RepairRule.created_at.asc())).scalars())


def find_matching_repair_rule(
    db: Session,
    *,
    rule_type: str,
    payload: dict[str, Any],
) -> RepairRule | None:
    for rule in list_enabled_repair_rules(db, rule_type=rule_type):
        if all(payload.get(key) == value for key, value in rule.match_payload.items()):
            return rule
    return None
