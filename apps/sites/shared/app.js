(() => {
  const cfg = window.STUDY_SITE_CONFIG;
  if (!cfg) {
    console.error("Missing STUDY_SITE_CONFIG");
    return;
  }

  const pageStart = Date.now();
  const API_BASE = cfg.apiBase;
  const $ = (id) => document.getElementById(id);

  const loginCard = $("loginCard");
  const taskCard = $("taskCard");
  const doneCard = $("doneCard");
  const loginErr = $("loginErr");
  const loginBtn = $("loginBtn");
  const loginSpinner = $("loginSpinner");
  const approveBtn = $("approveBtn");
  const approveSpinner = $("approveSpinner");

  const detailEls = {};
  (cfg.fields || []).forEach((field) => {
    detailEls[field.key] = $(field.elementId);
  });

  function showCard(name) {
    loginCard.style.display = name === "login" ? "block" : "none";
    taskCard.style.display = name === "task" ? "block" : "none";
    doneCard.style.display = name === "done" ? "block" : "none";
  }

  function appendLocalLog(line) {
    try {
      const key = `study_logs_${cfg.siteUrl}`;
      const existing = JSON.parse(localStorage.getItem(key) || "[]");
      existing.push({ ts: new Date().toISOString(), line });
      localStorage.setItem(key, JSON.stringify(existing.slice(-300)));
    } catch (_) {}
  }

  async function postJSON(path, payload) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      return res;
    } catch (err) {
      appendLocalLog(`POST ${path} failed: ${String(err)}`);
      return null;
    }
  }

  function getUserIdFromQueryOrForm() {
    const params = new URLSearchParams(window.location.search);
    const fromQuery = params.get("user_id");
    if (fromQuery) return Number(fromQuery);

    const username = $("acc").value.trim();
    if (/^\d+$/.test(username)) return Number(username);
    return null;
  }

  function setFallbackDetails() {
    const fallback = cfg.fallbackDetails || {};
    (cfg.fields || []).forEach((field) => {
      if (detailEls[field.key]) {
        detailEls[field.key].textContent = fallback[field.key] || "";
      }
    });
  }

  function setDetailsFromTaskType(taskType) {
    const details = (cfg.taskDetails && cfg.taskDetails[taskType]) || cfg.fallbackDetails || {};
    (cfg.fields || []).forEach((field) => {
      if (detailEls[field.key]) {
        detailEls[field.key].textContent = details[field.key] || "";
      }
    });
  }

  async function fetchCurrentAssignmentAndSetDetails(userId) {
    const res = await postJSON("/get-current-assignment", {
      user_id: userId,
      website: cfg.siteUrl
    });

    if (!res || !res.ok) {
      setFallbackDetails();
      return;
    }

    try {
      const data = await res.json();
      setDetailsFromTaskType(data.task_type || null);
    } catch (err) {
      appendLocalLog(`Bad JSON from /get-current-assignment: ${String(err)}`);
      setFallbackDetails();
    }
  }

  async function validateHardcodedLogin(username, password) {
    const numericId = /^\d+$/.test(username) ? Number(username) : null;
    if (numericId === null) return { ok: false, userId: null };

    const res = await postJSON("/get-user-credentials", {
      user_id: numericId,
      username
    });

    if (!res || !res.ok) {
      appendLocalLog("Credential lookup failed");
      return { ok: false, userId: numericId };
    }

    try {
      const data = await res.json();
      const ok = data && data.username === username && data.password === password;
      return { ok, userId: data?.id ?? numericId };
    } catch (err) {
      appendLocalLog(`Bad JSON from /get-user-credentials: ${String(err)}`);
      return { ok: false, userId: numericId };
    }
  }

  async function recordLoginEvent(userId, username) {
    appendLocalLog(`Login success for user ${userId} on ${cfg.siteUrl}`);
    await postJSON("/record-login-event", {
      user_id: userId,
      username,
      website: cfg.siteUrl
    });
  }

  async function recordCompletionEvent(userId, completionType) {
    appendLocalLog(`Completion event ${completionType} for user ${userId} on ${cfg.siteUrl}`);
    await postJSON("/record-complete-assignment-event", {
      user_id: userId,
      website: cfg.siteUrl,
      completion_type: completionType,
      elapsed_ms: Date.now() - pageStart
    });
  }

  loginBtn.onclick = async () => {
    const username = $("acc").value.trim();
    const password = $("pwd").value.trim();

    loginSpinner.style.display = "inline-block";
    loginBtn.disabled = true;

    setTimeout(async () => {
      const result = await validateHardcodedLogin(username, password);

      if (result.ok) {
        loginErr.style.display = "none";
        showCard("task");
        await recordLoginEvent(result.userId, username);
        await fetchCurrentAssignmentAndSetDetails(result.userId);
      } else {
        loginErr.textContent = "Invalid username or password.";
        loginErr.style.display = "block";
      }

      loginSpinner.style.display = "none";
      loginBtn.disabled = false;
    }, 500);
  };

  approveBtn.onclick = () => {
    const userId = getUserIdFromQueryOrForm();
    approveSpinner.style.display = "inline-block";
    approveBtn.disabled = true;
    approveBtn.innerHTML = '<span class="loading-spinner" style="display:inline-block;"></span>Processing Payment...';

    setTimeout(async () => {
      showCard("done");
      if (userId !== null) {
        await recordCompletionEvent(userId, "done");
      }
    }, 1500);
  };

  document.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && loginCard.style.display !== "none") {
      loginBtn.click();
    }
  });

  setFallbackDetails();
  showCard("login");
})();