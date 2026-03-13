from config import ALL_STUDY_SITES, GOOD_CERT_CHAIN, BAD_CERT_CHAIN
from study_logic import get_study_user, get_active_assignment_with_task


def get_certificate_chain_for_hostname(hostname: str):
    hostname = (hostname or "").strip()

    if hostname not in ALL_STUDY_SITES:
        return GOOD_CERT_CHAIN

    user = get_study_user()
    active = get_active_assignment_with_task(user["id"])
    if not active:
        return GOOD_CERT_CHAIN

    task = active["task"]
    is_cert_task = (task.get("phishing_type") or "").strip().upper() == "CERT"
    same_site = (task.get("site_url") or "") == hostname

    if is_cert_task and same_site:
        return BAD_CERT_CHAIN

    return GOOD_CERT_CHAIN