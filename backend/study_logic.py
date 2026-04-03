import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from config import (
    STUDY_USERNAME,
    STAGE_ORDER,
    STAGE_QUOTAS,
    STAGE_BLOCKLISTS,
    ALLOWED_COMPLETION_TYPES,
)
from db import supabase
from email_logic import send_task_email, send_stage_complete_email

logger = logging.getLogger("study_backend")
NY_TZ = ZoneInfo("America/New_York")


def now_ny():
    return datetime.now(NY_TZ)


def now_ny_iso():
    return now_ny().isoformat(timespec="seconds")


def seconds_to_hms(total_seconds: float) -> str:
    total_seconds = max(int(total_seconds), 0)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_study_user():
    result = (
        supabase.table("users")
        .select("*")
        .eq("username", STUDY_USERNAME)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise ValueError(f"Study user not found for username={STUDY_USERNAME}")
    return result.data[0]


def append_user_log_line(message: str):
    user = get_study_user()
    current_result = (
        supabase.table("users")
        .select("log_text")
        .eq("id", user["id"])
        .limit(1)
        .execute()
    )

    current_log = ""
    if current_result.data:
        current_log = current_result.data[0].get("log_text") or ""

    stamped_line = f"{now_ny_iso()}  {message}"
    new_log = f"{current_log}\n{stamped_line}" if current_log.strip() else stamped_line

    supabase.table("users").update({
        "log_text": new_log
    }).eq("id", user["id"]).execute()

    logger.info("Appended log line for user_id=%s: %s", user["id"], message)


# ---------------------------------------------------------------------------
# User study state helpers
# ---------------------------------------------------------------------------

def get_or_create_user_study_state(user_id: int):
    result = (
        supabase.table("user_study_state")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]

    created = (
        supabase.table("user_study_state")
        .insert({
            "user_id": user_id,
            "current_stage": "tutorial",
            "stage_started_at": now_ny_iso(),
            "stage_completed_at": None,
            "waiting_for_admin": False,
        })
        .execute()
    )
    return created.data[0]


def update_user_study_state(user_id: int, fields: dict):
    result = (
        supabase.table("user_study_state")
        .update(fields)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0] if result.data else None


# ---------------------------------------------------------------------------
# Task classification and querying
# ---------------------------------------------------------------------------

def classify_task(task: dict) -> str:
    if task.get("is_phishing") is False:
        return "regular"

    phishing_type = (task.get("phishing_type") or "").strip().upper()

    if phishing_type == "URL":
        return "url"
    if phishing_type == "EMAIL":
        return "email"
    if phishing_type == "CERT":
        return "cert"

    raise ValueError(f"Could not classify task_id={task.get('task_id')}")


def get_all_tasks():
    result = supabase.table("tasks").select("*").execute()
    return result.data or []


# ---------------------------------------------------------------------------
# Assignment queries
# ---------------------------------------------------------------------------

def get_all_assignments_with_tasks(user_id: int):
    result = (
        supabase.table("assignments")
        .select("*, tasks(*)")
        .eq("user_id", user_id)
        .execute()
    )
    return result.data or []


def get_incomplete_assignments_for_stage(user_id: int, stage: str):
    result = (
        supabase.table("assignments")
        .select("*, tasks(*)")
        .eq("user_id", user_id)
        .eq("stage", stage)
        .is_("completed_at", "null")
        .execute()
    )
    return result.data or []


def get_all_incomplete_assignments(user_id: int):
    result = (
        supabase.table("assignments")
        .select("*, tasks(*)")
        .eq("user_id", user_id)
        .is_("completed_at", "null")
        .execute()
    )
    return result.data or []


def get_used_task_ids(user_id: int):
    rows = get_all_assignments_with_tasks(user_id)
    return {row["task_id"] for row in rows if row.get("task_id") is not None}


# ---------------------------------------------------------------------------
# Stage completion checks
# ---------------------------------------------------------------------------

def get_completed_counts_for_stage(user_id: int, stage: str):
    rows = get_all_assignments_with_tasks(user_id)
    counts = {"regular": 0, "url": 0, "email": 0, "cert": 0}

    for row in rows:
        if row.get("stage") != stage:
            continue
        if row.get("completed_at") is None:
            continue
        task = row["tasks"]
        category = classify_task(task)
        counts[category] += 1

    return counts


def is_stage_complete(user_id: int, stage: str):
    counts = get_completed_counts_for_stage(user_id, stage)
    quota = STAGE_QUOTAS[stage]
    return all(counts[k] >= quota[k] for k in quota)


# ---------------------------------------------------------------------------
# Batch task selection for a stage
# ---------------------------------------------------------------------------

def select_tasks_for_stage(user_id: int, stage: str):
    """Pick all tasks needed for a stage at once, respecting quotas and blocklists."""
    quota = STAGE_QUOTAS[stage]
    used_task_ids = get_used_task_ids(user_id)
    all_tasks = get_all_tasks()
    blocked = set(STAGE_BLOCKLISTS[stage])

    newly_selected_ids: set[int] = set()
    selected_tasks: list[dict] = []

    for category, needed_count in quota.items():
        if needed_count <= 0:
            continue

        candidates = []
        for task in all_tasks:
            if classify_task(task) != category:
                continue
            site_url = task.get("site_url") or ""
            if category == "cert":
                if site_url not in blocked:
                    continue
            else:
                if site_url in blocked:
                    continue
            candidates.append(task)

        non_dup = [
            t for t in candidates
            if t["task_id"] not in used_task_ids
            and t["task_id"] not in newly_selected_ids
        ]

        chosen: list[dict] = []

        if len(non_dup) >= needed_count:
            chosen = random.sample(non_dup, needed_count)
        else:
            chosen = list(non_dup)
            remaining = needed_count - len(chosen)
            chosen_ids = {t["task_id"] for t in chosen}
            dup_pool = [t for t in candidates if t["task_id"] not in chosen_ids]
            if len(dup_pool) >= remaining:
                chosen.extend(random.sample(dup_pool, remaining))
            elif dup_pool:
                chosen.extend(dup_pool)
                still_needed = remaining - len(dup_pool)
                if still_needed > 0 and candidates:
                    chosen.extend(random.choices(candidates, k=still_needed))
            elif candidates:
                chosen.extend(random.choices(candidates, k=remaining))
            else:
                logger.warning(
                    "No candidates at all for stage=%s category=%s", stage, category
                )

        for t in chosen:
            newly_selected_ids.add(t["task_id"])
        selected_tasks.extend(chosen)

    return selected_tasks


# ---------------------------------------------------------------------------
# Assignment creation
# ---------------------------------------------------------------------------

def create_assignment(user: dict, task: dict, stage: str):
    result = (
        supabase.table("assignments")
        .insert({
            "user_id": user["id"],
            "task_id": task["task_id"],
            "sent_at": now_ny_iso(),
            "completed_at": None,
            "time_taken": None,
            "completion_type": None,
            "login_occurred": False,
            "username": user["username"],
            "stage": stage,
        })
        .execute()
    )
    return result.data[0]


def assign_entire_stage(user: dict, stage: str):
    """
    Select all tasks for a stage, create assignment rows, and send all emails.
    Skips if there are already incomplete assignments for this stage.
    Returns list of {"assignment": ..., "task": ...} dicts.
    """
    existing = get_incomplete_assignments_for_stage(user["id"], stage)
    if existing:
        logger.info(
            "Stage %s already has %d incomplete assignments — skipping batch assign",
            stage, len(existing),
        )
        return []

    tasks = select_tasks_for_stage(user["id"], stage)
    created: list[dict] = []

    for task in tasks:
        assignment = create_assignment(user, task, stage)
        created.append({"assignment": assignment, "task": task})

    for item in created:
        assignment = item["assignment"]
        task = item["task"]
        try:
            email_result = send_task_email(task, assignment)
            logger.info(
                "Task email sent for assignment_id=%s: %s",
                assignment["assignment_id"], email_result,
            )
        except Exception:
            logger.exception(
                "Failed to send task email for assignment_id=%s task_id=%s",
                assignment["assignment_id"], task["task_id"],
            )

    logger.info(
        "Assigned %d tasks for stage=%s user_id=%s",
        len(created), stage, user["id"],
    )
    return created


# ---------------------------------------------------------------------------
# Admin-triggered stage transitions
# ---------------------------------------------------------------------------

def start_study():
    user = get_study_user()
    state = get_or_create_user_study_state(user["id"])

    update_fields: dict = {}
    if state["current_stage"] != "tutorial":
        update_fields["current_stage"] = "tutorial"
    if state["waiting_for_admin"]:
        update_fields["waiting_for_admin"] = False
    if not state.get("stage_started_at"):
        update_fields["stage_started_at"] = now_ny_iso()

    if update_fields:
        update_user_study_state(user["id"], update_fields)

    created = assign_entire_stage(user, "tutorial")
    return {
        "stage": "tutorial",
        "assignments_created": len(created),
        "assignment_ids": [
            item["assignment"]["assignment_id"] for item in created
        ],
    }


def start_next_stage():
    user = get_study_user()
    state = get_or_create_user_study_state(user["id"])
    current_stage = state["current_stage"]

    if not state["waiting_for_admin"]:
        raise ValueError("Current stage is not waiting for admin")

    current_index = STAGE_ORDER.index(current_stage)
    if current_index == len(STAGE_ORDER) - 1:
        raise ValueError("Already at final stage")

    next_stage = STAGE_ORDER[current_index + 1]

    update_user_study_state(user["id"], {
        "current_stage": next_stage,
        "stage_started_at": now_ny_iso(),
        "stage_completed_at": None,
        "waiting_for_admin": False,
    })

    created = assign_entire_stage(user, next_stage)
    return {
        "stage": next_stage,
        "assignments_created": len(created),
        "assignment_ids": [
            item["assignment"]["assignment_id"] for item in created
        ],
    }


# ---------------------------------------------------------------------------
# Assignment-ID–based operations (the new primary interface)
# ---------------------------------------------------------------------------

def get_assignment_payload_by_id(assignment_id: int):
    """Return assignment+task details for a specific assignment, or None if invalid/completed."""
    user = get_study_user()

    result = (
        supabase.table("assignments")
        .select("*, tasks(*)")
        .eq("assignment_id", assignment_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    task = row["tasks"]

    if row.get("completed_at"):
        return None

    return {
        "assignment_id": row["assignment_id"],
        "task_id": task["task_id"],
        "task_name": task.get("task_name"),
        "task_type": task.get("task_type"),
        "site_url": task.get("site_url"),
        "email_text": task.get("email_text"),
        "email": task.get("email"),
        "is_phishing": task.get("is_phishing"),
        "phishing_type": task.get("phishing_type"),
        "stage": row.get("stage"),
        "login_occurred": row.get("login_occurred"),
        "sent_at": row.get("sent_at"),
    }


def record_login_for_assignment(assignment_id: int, website: str):
    """Mark login_occurred for a specific incomplete assignment if the site matches."""
    user = get_study_user()

    result = (
        supabase.table("assignments")
        .select("*, tasks(*)")
        .eq("assignment_id", assignment_id)
        .eq("user_id", user["id"])
        .is_("completed_at", "null")
        .limit(1)
        .execute()
    )

    if not result.data:
        return False

    row = result.data[0]
    task = row["tasks"]

    if (task.get("site_url") or "") != website:
        return False

    supabase.table("assignments").update({
        "login_occurred": True
    }).eq("assignment_id", assignment_id).execute()

    logger.info(
        "Recorded login for assignment_id=%s website=%s",
        assignment_id, website,
    )
    return True


def complete_assignment_by_id(assignment_id: int, completion_type: str, website: str | None = None):
    """
    Complete a specific assignment by its ID.
    After completion, check if the entire stage is now done.
    """
    if completion_type not in ALLOWED_COMPLETION_TYPES:
        raise ValueError(f"Invalid completion_type={completion_type}")

    user = get_study_user()

    result = (
        supabase.table("assignments")
        .select("*, tasks(*)")
        .eq("assignment_id", assignment_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )

    if not result.data:
        raise ValueError(f"Assignment {assignment_id} not found for study user")

    row = result.data[0]
    task = row["tasks"]

    if row.get("completed_at"):
        raise ValueError(f"Assignment {assignment_id} is already completed")

    if website is not None:
        active_site = (task.get("site_url") or "").strip()
        requested_site = (website or "").strip()
        if active_site != requested_site:
            raise ValueError(
                f"Completion website mismatch: active_site={active_site!r} requested_site={requested_site!r}"
            )

    sent_at = row["sent_at"]
    if not sent_at:
        raise ValueError("Assignment is missing sent_at")

    sent_dt = datetime.fromisoformat(sent_at).replace(tzinfo=NY_TZ)
    completed_dt = now_ny()
    elapsed_seconds = (completed_dt - sent_dt).total_seconds()

    updated = (
        supabase.table("assignments")
        .update({
            "completed_at": completed_dt.isoformat(timespec="seconds"),
            "time_taken": seconds_to_hms(elapsed_seconds),
            "completion_type": completion_type,
        })
        .eq("assignment_id", assignment_id)
        .execute()
    )

    logger.info(
        "Completed assignment_id=%s with completion_type=%s",
        assignment_id, completion_type,
    )

    stage = row.get("stage")
    if stage and is_stage_complete(user["id"], stage):
        state = get_or_create_user_study_state(user["id"])
        if not state.get("waiting_for_admin"):
            update_user_study_state(user["id"], {
                "waiting_for_admin": True,
                "stage_completed_at": now_ny_iso(),
            })
            try:
                email_result = send_stage_complete_email(stage)
                logger.info("Stage complete email sent: %s", email_result)
            except Exception:
                logger.exception("Failed to send stage complete email for stage=%s", stage)

    return updated.data[0]


# ---------------------------------------------------------------------------
# Legacy compat: site-based active-assignment operations
# ---------------------------------------------------------------------------

def get_active_assignment_with_task(user_id: int):
    """Legacy: returns the first incomplete assignment (used by cert_logic compat)."""
    result = (
        supabase.table("assignments")
        .select("*, tasks(*)")
        .eq("user_id", user_id)
        .is_("completed_at", "null")
        .limit(1)
        .execute()
    )
    if not result.data:
        return None

    row = result.data[0]
    return {
        "assignment": row,
        "task": row["tasks"],
    }


def complete_active_assignment_compat(
    completion_type: str,
    website: str | None = None,
    assignment_id: int | None = None,
):
    """
    Backward-compat wrapper used by /complete-task.
    Prefers assignment_id if given; falls back to matching by website.
    """
    if assignment_id:
        completed = complete_assignment_by_id(assignment_id, completion_type, website)
    else:
        if completion_type not in ALLOWED_COMPLETION_TYPES:
            raise ValueError(f"Invalid completion_type={completion_type}")

        user = get_study_user()
        rows = get_all_incomplete_assignments(user["id"])

        if not rows:
            raise ValueError("No active assignment")

        target = None
        if website:
            for row in rows:
                task = row["tasks"]
                if (task.get("site_url") or "").strip() == website.strip():
                    target = row
                    break

        if not target:
            target = rows[0]

        completed = complete_assignment_by_id(
            target["assignment_id"], completion_type, website
        )

    return {"completed_assignment": completed}


def get_user_study_state_payload():
    user = get_study_user()
    state = get_or_create_user_study_state(user["id"])
    return state
