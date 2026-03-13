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
    """
    Append a timestamped line to users.log_text for the hardcoded study user.
    """
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


def complete_active_assignment_compat(completion_type: str, website: str | None = None):
    """
    Compatibility wrapper for older extension/frontend behavior.
    Uses the same active-assignment completion logic.
    """
    completed_assignment = complete_active_assignment(completion_type, website=website)

    user = get_study_user()
    next_result = assign_next_task_if_possible(user)

    logger.info(
        "Compat complete-task called website=%s completion_type=%s assignment_id=%s next_result=%s",
        website,
        completion_type,
        completed_assignment["assignment_id"],
        next_result,
    )

    return {
        "completed_assignment": completed_assignment,
        "next_result": next_result,
    }

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


def get_active_assignment_with_task(user_id: int):
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


def get_all_assignments_with_tasks(user_id: int):
    result = (
        supabase.table("assignments")
        .select("*, tasks(*)")
        .eq("user_id", user_id)
        .execute()
    )
    return result.data or []


def get_used_task_ids(user_id: int):
    rows = get_all_assignments_with_tasks(user_id)
    return {row["task_id"] for row in rows if row.get("task_id") is not None}


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


def get_remaining_categories_for_stage(user_id: int, stage: str):
    counts = get_completed_counts_for_stage(user_id, stage)
    quota = STAGE_QUOTAS[stage]
    return [k for k in quota if counts[k] < quota[k]]


def get_candidate_tasks(user_id: int, stage: str, category: str, allow_duplicates: bool = False):
    blocked = set(STAGE_BLOCKLISTS[stage])
    used_task_ids = get_used_task_ids(user_id)
    all_tasks = get_all_tasks()

    candidates = []

    for task in all_tasks:
        if not allow_duplicates and task["task_id"] in used_task_ids:
            continue

        task_category = classify_task(task)
        if task_category != category:
            continue

        site_url = task.get("site_url") or ""

        if category == "cert":
            if site_url not in blocked:
                continue
        else:
            if site_url in blocked:
                continue

        candidates.append(task)

    return candidates


def choose_next_task(user_id: int, stage: str):
    remaining_categories = get_remaining_categories_for_stage(user_id, stage)
    if not remaining_categories:
        return None

    random.shuffle(remaining_categories)

    # First pass: avoid duplicates
    for category in remaining_categories:
        candidates = get_candidate_tasks(
            user_id=user_id,
            stage=stage,
            category=category,
            allow_duplicates=False,
        )
        if candidates:
            task = random.choice(candidates)
            logger.info(
                "Chose NON-DUPLICATE task_id=%s for user_id=%s stage=%s category=%s",
                task["task_id"], user_id, stage, category
            )
            return task

    # Second pass: allow duplicates only if necessary
    for category in remaining_categories:
        candidates = get_candidate_tasks(
            user_id=user_id,
            stage=stage,
            category=category,
            allow_duplicates=True,
        )
        if candidates:
            task = random.choice(candidates)
            logger.warning(
                "Chose DUPLICATE-ALLOWED task_id=%s for user_id=%s stage=%s category=%s because no non-duplicate candidate existed",
                task["task_id"], user_id, stage, category
            )
            return task

    raise ValueError(f"No candidate tasks available at all for user_id={user_id}, stage={stage}")


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


def assign_next_task_if_possible(user: dict):
    active = get_active_assignment_with_task(user["id"])
    if active:
        return {
            "created": False,
            "reason": "active_assignment_exists",
            "assignment": active["assignment"],
            "task": active["task"],
        }

    state = get_or_create_user_study_state(user["id"])
    stage = state["current_stage"]

    if state["waiting_for_admin"]:
        return {
            "created": False,
            "reason": "waiting_for_admin",
            "stage": stage,
        }

    if is_stage_complete(user["id"], stage):
        update_user_study_state(user["id"], {
            "waiting_for_admin": True,
            "stage_completed_at": now_ny_iso(),
        })

        try:
            email_result = send_stage_complete_email(stage)
            logger.info("Stage complete email sent: %s", email_result)
        except Exception as e:
            logger.exception("Failed to send stage complete email for stage=%s", stage)

        return {
            "created": False,
            "reason": "stage_complete",
            "stage": stage,
        }

    task = choose_next_task(user["id"], stage)
    if not task:
        update_user_study_state(user["id"], {
            "waiting_for_admin": True,
            "stage_completed_at": now_ny_iso(),
        })

        try:
            email_result = send_stage_complete_email(stage)
            logger.info("Stage complete email sent: %s", email_result)
        except Exception as e:
            logger.exception("Failed to send stage complete email for stage=%s", stage)

        return {
            "created": False,
            "reason": "stage_complete",
            "stage": stage,
        }

    assignment = create_assignment(user, task, stage)
    logger.info("Assigned task_id=%s to user_id=%s for stage=%s", task["task_id"], user["id"], stage)

    try:
        email_result = send_task_email(task)
        logger.info("Task email result: %s", email_result)
    except Exception as e:
        logger.exception("Failed to send task email for task_id=%s", task["task_id"])

    return {
        "created": True,
        "stage": stage,
        "assignment": assignment,
        "task": task,
    }


def start_study():
    user = get_study_user()
    state = get_or_create_user_study_state(user["id"])

    update_fields = {}
    if state["current_stage"] != "tutorial":
        update_fields["current_stage"] = "tutorial"
    if state["waiting_for_admin"]:
        update_fields["waiting_for_admin"] = False
    if not state.get("stage_started_at"):
        update_fields["stage_started_at"] = now_ny_iso()

    if update_fields:
        update_user_study_state(user["id"], update_fields)

    return assign_next_task_if_possible(user)


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

    return assign_next_task_if_possible(user)


def record_login_if_matches_active(website: str):
    user = get_study_user()
    active = get_active_assignment_with_task(user["id"])
    if not active:
        return False

    assignment = active["assignment"]
    task = active["task"]

    if (task.get("site_url") or "") != website:
        return False

    supabase.table("assignments").update({
        "login_occurred": True
    }).eq("assignment_id", assignment["assignment_id"]).execute()

    logger.info(
        "Recorded login for user_id=%s assignment_id=%s website=%s",
        user["id"],
        assignment["assignment_id"],
        website,
    )
    return True


def complete_active_assignment(completion_type: str, website: str | None = None):
    if completion_type not in ALLOWED_COMPLETION_TYPES:
        raise ValueError(f"Invalid completion_type={completion_type}")

    user = get_study_user()
    active = get_active_assignment_with_task(user["id"])
    if not active:
        raise ValueError("No active assignment")

    assignment = active["assignment"]
    task = active["task"]

    if website is not None:
        active_site = (task.get("site_url") or "").strip()
        requested_site = (website or "").strip()
        if active_site != requested_site:
            raise ValueError(
                f"Completion website mismatch: active_site={active_site!r} requested_site={requested_site!r}"
            )

    sent_at = assignment["sent_at"]
    if not sent_at:
        raise ValueError("Active assignment is missing sent_at")

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
        .eq("assignment_id", assignment["assignment_id"])
        .execute()
    )

    logger.info(
        "Completed assignment_id=%s with completion_type=%s",
        assignment["assignment_id"],
        completion_type,
    )

    return updated.data[0]


def get_current_assignment_payload():
    user = get_study_user()
    active = get_active_assignment_with_task(user["id"])

    if not active:
        return None

    assignment = active["assignment"]
    task = active["task"]

    return {
        "assignment_id": assignment["assignment_id"],
        "task_id": task["task_id"],
        "task_name": task.get("task_name"),
        "task_type": task.get("task_type"),
        "site_url": task.get("site_url"),
        "email_text": task.get("email_text"),
        "email": task.get("email"),
        "is_phishing": task.get("is_phishing"),
        "phishing_type": task.get("phishing_type"),
        "stage": assignment.get("stage"),
        "login_occurred": assignment.get("login_occurred"),
        "sent_at": assignment.get("sent_at"),
    }


def get_user_study_state_payload():
    user = get_study_user()
    state = get_or_create_user_study_state(user["id"])
    return state