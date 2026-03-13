from config import ALL_STUDY_SITES, GOOD_CERT_CHAIN, BAD_CERT_CHAIN
from study_logic import get_study_user, get_active_assignment_with_task


def normalize_hostname(hostname: str) -> str:
    host = (hostname or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def get_certificate_chain_for_hostname(hostname: str):
    host = normalize_hostname(hostname)

    # For non-study sites, always return the good chain for now.
    if host not in ALL_STUDY_SITES:
        return GOOD_CERT_CHAIN

    user = get_study_user()
    active = get_active_assignment_with_task(user["id"])

    if not active:
        return GOOD_CERT_CHAIN

    task = active["task"]
    is_cert_task = (task.get("phishing_type") or "").strip().upper() == "CERT"
    same_site = normalize_hostname(task.get("site_url") or "") == host

    if is_cert_task and same_site:
        return BAD_CERT_CHAIN

    return GOOD_CERT_CHAIN