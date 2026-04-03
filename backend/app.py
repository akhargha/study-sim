import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request
from flask_cors import CORS

from config import LOG_FILE, EXTENSION_ID
from study_logic import (
    start_study,
    start_next_stage,
    get_assignment_payload_by_id,
    record_login_for_assignment,
    complete_assignment_by_id,
    complete_active_assignment_compat,
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

    # ------------------------------------------------------------------
    # Health / state
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Admin: stage transitions (assigns entire stage in one batch)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Assignment-ID–based site endpoints
    # ------------------------------------------------------------------

    @app.get("/api/get-assignment/<int:assignment_id>")
    def api_get_assignment(assignment_id):
        try:
            payload = get_assignment_payload_by_id(assignment_id)
            return jsonify({"ok": True, "assignment": payload})
        except Exception as e:
            logger.exception("get-assignment failed for id=%s", assignment_id)
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/api/record-login-event")
    def api_record_login_event():
        try:
            body = request.get_json(force=True) or {}
            assignment_id = body.get("assignment_id")
            website = body.get("website", "")

            if not assignment_id:
                return jsonify({"ok": False, "error": "assignment_id required"}), 400

            updated = record_login_for_assignment(int(assignment_id), website)
            logger.info(
                "record-login-event assignment_id=%s website=%s updated=%s",
                assignment_id, website, updated,
            )
            return jsonify({"ok": True, "updated": updated})
        except Exception as e:
            logger.exception("record-login-event failed")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/api/record-complete-assignment-event")
    def api_record_complete_assignment_event():
        try:
            body = request.get_json(force=True) or {}
            assignment_id = body.get("assignment_id")
            completion_type = body.get("completion_type", "")
            website = body.get("website")

            if not assignment_id:
                return jsonify({"ok": False, "error": "assignment_id required"}), 400

            completed = complete_assignment_by_id(
                assignment_id=int(assignment_id),
                completion_type=completion_type,
                website=website,
            )

            logger.info(
                "record-complete-assignment-event assignment_id=%s completion_type=%s",
                assignment_id, completion_type,
            )

            return jsonify({
                "ok": True,
                "completed_assignment": completed,
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

    # ------------------------------------------------------------------
    # Extension compatibility routes
    # ------------------------------------------------------------------

    @app.post("/log")
    def extension_log():
        try:
            body = request.get_json(force=True) or {}
            text = body.get("text", "")
            timestamp = body.get("timestamp")
            extension_id = request.headers.get("X-Extension-ID", "")

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
            assignment_id = body.get("assignment_id")

            result = complete_active_assignment_compat(
                completion_type=completion_type,
                website=site_url or None,
                assignment_id=int(assignment_id) if assignment_id else None,
            )

            return jsonify({
                "status": "completed",
                "completed_assignment": result["completed_assignment"],
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
