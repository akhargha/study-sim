from config import ALL_STUDY_SITES, GOOD_CERT_CHAIN, BAD_CERT_CHAIN
from study_logic import get_study_user, get_all_incomplete_assignments


def normalize_hostname(hostname: str) -> str:
    host = (hostname or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def get_certificate_chain_for_hostname(hostname: str):
    host = normalize_hostname(hostname)

    if host not in ALL_STUDY_SITES:
        return GOOD_CERT_CHAIN

    user = get_study_user()
    incomplete = get_all_incomplete_assignments(user["id"])

    for row in incomplete:
        task = row["tasks"]
        is_cert_task = (task.get("phishing_type") or "").strip().upper() == "CERT"
        same_site = normalize_hostname(task.get("site_url") or "") == host
        if is_cert_task and same_site:
            return BAD_CERT_CHAIN

    return GOOD_CERT_CHAIN
