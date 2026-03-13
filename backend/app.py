import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request
from flask_cors import CORS

from config import LOG_FILE, EXTENSION_ID
from study_logic import (
    start_study,
    start_next_stage,
    get_current_assignment_payload,
    record_login_if_matches_active,
    complete_active_assignment,
    complete_active_assignment_compat,
    assign_next_task_if_possible,
    get_study_user,
    get_user_study_state_payload,
    append_user_log_line,
)
from cert_logic import get_certificate_chain_for_hostname


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)

    logger = logging.getLogger("study_backend")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/api/current-user-state")
    def current_user_state():
        try:
            return jsonify({"ok": True, "state": get_user_study_state_payload()})
        except Exception as e:
            logger.exception("current-user-state failed")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/api/start-study")
    def api_start_study():
        try:
            result = start_study()
            logger.info("start-study result=%s", result)
            return jsonify({"ok": True, **result})
        except Exception as e:
            logger.exception("start-study failed")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/api/start-next-stage")
    def api_start_next_stage():
        try:
            result = start_next_stage()
            logger.info("start-next-stage result=%s", result)
            return jsonify({"ok": True, **result})
        except Exception as e:
            logger.exception("start-next-stage failed")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.get("/api/get-current-assignment")
    def api_get_current_assignment():
        try:
            payload = get_current_assignment_payload()
            return jsonify({"ok": True, "assignment": payload})
        except Exception as e:
            logger.exception("get-current-assignment failed")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/api/record-login-event")
    def api_record_login_event():
        try:
            body = request.get_json(force=True) or {}
            website = body.get("website", "")
            updated = record_login_if_matches_active(website)
            logger.info("record-login-event website=%s updated=%s", website, updated)
            return jsonify({"ok": True, "updated": updated})
        except Exception as e:
            logger.exception("record-login-event failed")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/api/record-complete-assignment-event")
    def api_record_complete_assignment_event():
        try:
            body = request.get_json(force=True) or {}
            completion_type = body.get("completion_type", "")

            completed_assignment = complete_active_assignment(completion_type)

            user = get_study_user()
            next_result = assign_next_task_if_possible(user)

            logger.info(
                "record-complete-assignment-event completion_type=%s completed_assignment_id=%s next_result=%s",
                completion_type,
                completed_assignment["assignment_id"],
                next_result,
            )

            return jsonify({
                "ok": True,
                "completed_assignment": completed_assignment,
                "next_result": next_result,
            })
        except Exception as e:
            logger.exception("record-complete-assignment-event failed")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/api/get-certificate-chain")
    def api_get_certificate_chain():
        try:
            body = request.get_json(force=True) or {}
            hostname = body.get("hostname", "")
            chain = get_certificate_chain_for_hostname(hostname)
            return jsonify({"ok": True, "hostname": hostname, "chain": chain})
        except Exception as e:
            logger.exception("get-certificate-chain failed")
            return jsonify({"ok": False, "error": str(e)}), 500

    # ---------------------------
    # Extension compatibility routes
    # ---------------------------

    @app.post("/log")
    def extension_log():
        try:
            body = request.get_json(force=True) or {}
            text = body.get("text", "")
            timestamp = body.get("timestamp")
            extension_id = request.headers.get("X-Extension-ID", "")

            # In this environment, just log it. You can enforce the header later if you want.
            if extension_id and extension_id != EXTENSION_ID:
                logger.warning("Unexpected extension id: %s", extension_id)

            if not isinstance(text, str) or not text.strip():
                return jsonify({"error": "bad payload"}), 400

            append_user_log_line(text.strip())
            logger.info("Extension /log accepted timestamp=%s text=%s", timestamp, text)
            return jsonify({"status": "logged"}), 200
        except Exception as e:
            logger.exception("/log failed")
            return jsonify({"error": str(e)}), 500

    @app.post("/complete-task")
    def extension_complete_task():
        try:
            body = request.get_json(force=True) or {}
            site_url = body.get("site_url", "")
            completion_type = body.get("completion_type", "")

            result = complete_active_assignment_compat(
                completion_type=completion_type,
                website=site_url,
            )

            return jsonify({
                "status": "completed",
                "next_task": result["next_result"],
            }), 200
        except Exception as e:
            logger.exception("/complete-task failed")
            return jsonify({"error": str(e)}), 500

    @app.get("/certificate_chain/<path:hostname>")
    def extension_certificate_chain(hostname):
        try:
            chain = get_certificate_chain_for_hostname(hostname)
            return jsonify({
                "status": True,
                "output": chain,
            }), 200
        except Exception as e:
            logger.exception("/certificate_chain failed")
            return jsonify({
                "status": False,
                "output": None,
                "error": str(e),
            }), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5005, debug=True)