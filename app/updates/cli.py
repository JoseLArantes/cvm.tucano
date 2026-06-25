from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.services.normalizacao import datetime_para_string_br
from app.updates.models import PendingUpdate, PendingUpdateMember, UpdateSession, UpdateSessionItem
from app.updates.service import (
    add_session_item,
    create_session,
    discard_update,
    run_deep_analysis,
    run_scanner,
    trigger_session,
    trigger_update,
)

SESSION_FILE = Path("data/temp_updates/.cli_session")


def get_active_session_key() -> str | None:
    if SESSION_FILE.exists():
        try:
            return SESSION_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return None


def save_session_key(key: str) -> None:
    try:
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.write_text(key, encoding="utf-8")
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CVM Data Updates Service CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scanner
    scanner_parser = subparsers.add_parser("scanner", help="Scanner commands")
    scanner_sub = scanner_parser.add_subparsers(dest="subcommand", required=True)
    scanner_sub.add_parser("run", help="Run HTTP HEAD probe scanner")
    scanner_sub.add_parser("status", help="Get status of updates scanner")

    # pending
    pending_parser = subparsers.add_parser("pending", help="Manage pending updates")
    pending_sub = pending_parser.add_subparsers(dest="subcommand", required=True)
    pending_sub.add_parser("list", help="List all pending updates")
    
    show_p = pending_sub.add_parser("show", help="Show details of an update and its members")
    show_p.add_argument("id", type=str, help="Pending Update UUID")
    
    analyze_p = pending_sub.add_parser("analyze", help="Perform deep member analysis on a pending update")
    analyze_p.add_argument("id", type=str, help="Pending Update UUID")
    
    trigger_p = pending_sub.add_parser("trigger", help="Trigger ingestion for a pending update")
    trigger_p.add_argument("id", type=str, help="Pending Update UUID")
    
    discard_p = pending_sub.add_parser("discard", help="Discard a pending update")
    discard_p.add_argument("id", type=str, help="Pending Update UUID")

    # session
    session_parser = subparsers.add_parser("session", help="Manage update sessions")
    session_sub = session_parser.add_subparsers(dest="subcommand", required=True)
    session_sub.add_parser("create", help="Create a new update session")
    
    add_p = session_sub.add_parser("add", help="Add a pending update to session")
    add_p.add_argument("id", type=str, help="Pending Update UUID")
    add_p.add_argument("--key", type=str, default=None, help="Update session key")
    
    list_p = session_sub.add_parser("list", help="List items in session")
    list_p.add_argument("--key", type=str, default=None, help="Update session key")
    
    trigger_s_p = session_sub.add_parser("trigger", help="Trigger all selected updates in session")
    trigger_s_p.add_argument("--key", type=str, default=None, help="Update session key")

    # trigger-all
    subparsers.add_parser("trigger-all", help="Trigger all updates in ready_for_ingestion status")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        if args.command == "scanner":
            if args.subcommand == "run":
                print("Running updates scanner...")
                result = run_scanner(db)
                detected = result.get("detected_updates", [])
                print(f"Scanner run complete. Detected {len(detected)} new updates.")
                for update_item in detected:
                    print(f" - [{update_item.fonte}] Year: {update_item.ano} | URL: {update_item.artifact_url}")
            
            elif args.subcommand == "status":
                stmt = select(func.max(PendingUpdate.last_probe_timestamp))
                last_run = db.scalar(stmt)
                print("Scanner status: IDLE")
                print(f"Last Probe Run: {datetime_para_string_br(last_run) if last_run else 'Never'}")

        elif args.command == "pending":
            if args.subcommand == "list":
                stmt_list_pending = select(PendingUpdate).order_by(PendingUpdate.detection_timestamp.desc())
                pending_list = db.scalars(stmt_list_pending).all()
                if not pending_list:
                    print("No pending updates found.")
                else:
                    print(f"{'ID':<38} | {'Source':<10} | {'Year':<6} | {'Status':<20} | {'Detected At'}")
                    print("-" * 90)
                    for p_item in pending_list:
                        yr = str(p_item.ano) if p_item.ano is not None else "N/A"
                        print(
                            f"{str(p_item.id):<38} | {p_item.fonte:<10} | {yr:<6} | {p_item.status:<20} | "
                            f"{datetime_para_string_br(p_item.detection_timestamp)}"
                        )

            elif args.subcommand == "show":
                update_id = uuid.UUID(args.id)
                pending_detail = db.get(PendingUpdate, update_id)
                if pending_detail is None:
                    print(f"Error: PendingUpdate {args.id} not found.")
                    return 1
                
                print(f"Pending Update: {pending_detail.id}")
                print(f"  Source:      {pending_detail.fonte}")
                print(f"  Year:        {pending_detail.ano}")
                print(f"  Status:      {pending_detail.status}")
                print(f"  Detected:    {datetime_para_string_br(pending_detail.detection_timestamp)}")
                print(f"  Artifact:    {pending_detail.artifact_url}")
                print(f"  Summary:     {pending_detail.change_summary}")
                
                stmt_members = select(PendingUpdateMember).where(PendingUpdateMember.pending_update_id == update_id)
                members = db.scalars(stmt_members).all()
                if members:
                    print("\nMembers details:")
                    print(f"  {'Member Name':<45} | {'Category':<10} | {'Status':<15} | {'Rows (Prev -> Curr)'}")
                    print("  " + "-" * 95)
                    for m in members:
                        p_rows = str(m.previous_row_count) if m.previous_row_count is not None else "0"
                        c_rows = str(m.current_row_count) if m.current_row_count is not None else "0"
                        print(f"  {m.member_name:<45} | {m.change_category:<10} | {m.status:<15} | {p_rows} -> {c_rows}")

            elif args.subcommand == "analyze":
                update_id = uuid.UUID(args.id)
                print(f"Starting deep analysis for update {update_id}...")
                analyzed_pending = run_deep_analysis(db, update_id)
                print(f"Deep analysis finished. Status: {analyzed_pending.status}")
                print(f"Change summary: {analyzed_pending.change_summary}")

            elif args.subcommand == "trigger":
                update_id = uuid.UUID(args.id)
                print(f"Triggering ingestion for update {update_id}...")
                task_id = trigger_update(db, update_id, user="cli")
                print(f"Successfully triggered. Celery Ingestion Task ID: {task_id}")

            elif args.subcommand == "discard":
                update_id = uuid.UUID(args.id)
                discard_update(db, update_id)
                print(f"PendingUpdate {update_id} marked as discarded.")

        elif args.command == "session":
            if args.subcommand == "create":
                sess = create_session(db, user_id="cli")
                save_session_key(sess.session_key)
                print(f"Created new update session: {sess.session_key}")
                print(f"Expires at: {datetime_para_string_br(sess.expires_at)}")
                print("Session key saved locally. Sub-commands will use it automatically.")

            elif args.subcommand == "add":
                update_id = uuid.UUID(args.id)
                key = args.key or get_active_session_key()
                if not key:
                    print("Error: No active session key found. Run 'session create' first.")
                    return 1
                add_session_item(db, key, update_id)
                print(f"Added pending update {update_id} to session {key}")

            elif args.subcommand == "list":
                key = args.key or get_active_session_key()
                if not key:
                    print("Error: No active session key found. Run 'session create' first.")
                    return 1
                stmt_sess = select(UpdateSession).where(UpdateSession.session_key == key)
                sess_detail = db.scalar(stmt_sess)
                if sess_detail is None:
                    print(f"Error: Session {key} not found.")
                    return 1
                
                stmt_items = select(UpdateSessionItem).where(UpdateSessionItem.session_id == sess_detail.id)
                items = db.scalars(stmt_items).all()
                print(f"Session: {sess_detail.session_key} ({sess_detail.status})")
                print(f"Expires: {datetime_para_string_br(sess_detail.expires_at)}")
                print(f"Items count: {len(items)}")
                print("-" * 60)
                for sess_item in items:
                    print(f" - PendingUpdate ID: {sess_item.pending_update_id} | Action: {sess_item.action}")

            elif args.subcommand == "trigger":
                key = args.key or get_active_session_key()
                if not key:
                    print("Error: No active session key found. Run 'session create' first.")
                    return 1
                print(f"Triggering updates in session {key}...")
                task_ids = trigger_session(db, key, user="cli")
                print(f"Successfully triggered {len(task_ids)} updates. Celery tasks: {task_ids}")

        elif args.command == "trigger-all":
            stmt_ready = select(PendingUpdate).where(PendingUpdate.status == "ready_for_ingestion")
            ready = db.scalars(stmt_ready).all()
            if not ready:
                print("No pending updates in 'ready_for_ingestion' status.")
            else:
                print(f"Found {len(ready)} ready updates. Triggering...")
                for ready_item in ready:
                    try:
                        tid = trigger_update(db, ready_item.id, user="cli")
                        print(f" - [{ready_item.fonte}] Year: {ready_item.ano} | Celery Task ID: {tid}")
                    except Exception as e:
                        print(f" - [{ready_item.fonte}] Year: {ready_item.ano} | Failed: {e}")

    except Exception as exc:
        print(f"CLI Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
