(() => {
  const cfg = window.STUDY_SITE_CONFIG;
  const API_BASE = cfg.apiBase;
  const $ = (id) => document.getElementById(id);

  const loginCard = $("loginCard");
  const taskCard = $("taskCard");
  const doneCard = $("doneCard");
  const loginErr = $("loginErr");

  const BRAND_DOMAIN_GROUPS = {
    citytrust: ["citytrust.com", "citytrustbank.com", "citytrustbanking.com", "citytrut.com", "citytrvst.com", "cltytrust.com"],
    meridiansuites: ["merdiansuites.com", "meridainsuites.com", "meridiansuite.com", "meridiansuites.co", "meridiansuites.com", "rneridiansuites.com"],
    cloudjetairways: ["cl0udjetairways.com", "cloudjetairway.com", "cloudjetairways.com", "cloudjetarways.com", "cloudjettairways.com", "cioudjetairways.com"],
  };

  function getAssignmentIdFromPath() {
    const parts = window.location.pathname.split("/").filter(Boolean);
    if (parts.length === 2 && parts[0] === "a") {
      const id = Number(parts[1]);
      return Number.isFinite(id) && id > 0 ? id : null;
    }
    return null;
  }

  const assignmentId = getAssignmentIdFromPath();
  console.log("[study] assignmentId from URL:", assignmentId, "path:", window.location.pathname);

  function getBrandForDomain(domain) {
    if (!domain) return null;
    const normalized = String(domain).toLowerCase();
    for (const [brand, domains] of Object.entries(BRAND_DOMAIN_GROUPS)) {
      if (domains.includes(normalized)) {
        return brand;
      }
    }
    return null;
  }

  function isSameBrandTask(assignmentSite) {
    if (!assignmentSite) return true;
    const currentBrand = getBrandForDomain(cfg.siteUrl);
    const assignmentBrand = getBrandForDomain(assignmentSite);
    if (!currentBrand || !assignmentBrand) return true;
    return currentBrand === assignmentBrand;
  }

  function showCard(name) {
    loginCard.style.display = name === "login" ? "block" : "none";
    taskCard.style.display = name === "task" ? "block" : "none";
    doneCard.style.display = name === "done" ? "block" : "none";
  }

  function setFallbackDetails() {
    console.log("[study] Setting FALLBACK details");
    for (const field of cfg.fields) {
      const el = $(field.elementId);
      if (el) {
        el.textContent = cfg.fallbackDetails[field.key] || "";
      }
    }
  }

  function setTaskDetails(taskType) {
    const details = cfg.taskDetails[taskType];
    if (!details) {
      console.log("[study] No taskDetails for taskType:", taskType, "— using fallback");
      setFallbackDetails();
      return;
    }
    console.log("[study] Setting task details for taskType:", taskType);
    for (const field of cfg.fields) {
      const el = $(field.elementId);
      if (el) {
        el.textContent = details[field.key] || "";
      }
    }
  }

  async function fetchAssignment() {
    if (!assignmentId) {
      console.log("[study] No assignmentId — showing fallback");
      setFallbackDetails();
      return;
    }

    const url = `${API_BASE}/api/get-assignment/${assignmentId}`;
    console.log("[study] Fetching assignment from:", url);

    try {
      const res = await fetch(url);
      const data = await res.json();
      console.log("[study] API response:", { ok: res.ok, status: res.status, data });

      if (!res.ok) {
        console.log("[study] Response not ok — showing fallback");
        setFallbackDetails();
        return;
      }

      if (!data.assignment) {
        console.log("[study] No assignment in response (null/completed) — showing fallback");
        setFallbackDetails();
        return;
      }

      const taskType = data.assignment.task_type || null;
      const assignmentSite = data.assignment.site_url || null;

      console.log("[study] Assignment data:", { taskType, assignmentSite, siteUrl: cfg.siteUrl });

      if (!isSameBrandTask(assignmentSite)) {
        console.log("[study] Brand mismatch — showing fallback");
        setFallbackDetails();
        return;
      }

      setTaskDetails(taskType);
    } catch (err) {
      console.error("[study] fetchAssignment error:", err);
      localStorage.setItem("study_last_error", `fetchAssignment: ${String(err)}`);
      setFallbackDetails();
    }
  }

  async function recordLoginEvent() {
    if (!assignmentId) return;

    try {
      const res = await fetch(`${API_BASE}/api/record-login-event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          assignment_id: assignmentId,
          website: cfg.siteUrl,
        }),
      });
      const data = await res.json();
      console.log("[study] recordLoginEvent response:", data);
    } catch (err) {
      console.error("[study] recordLoginEvent error:", err);
      localStorage.setItem("study_last_error", `recordLoginEvent: ${String(err)}`);
    }
  }

  async function completeAssignment(completionType) {
    if (!assignmentId) return;

    try {
      const res = await fetch(`${API_BASE}/api/record-complete-assignment-event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          assignment_id: assignmentId,
          website: cfg.siteUrl,
          completion_type: completionType,
        }),
      });
      const data = await res.json();
      console.log("[study] completeAssignment response:", data);
    } catch (err) {
      console.error("[study] completeAssignment error:", err);
      localStorage.setItem("study_last_error", `completeAssignment: ${String(err)}`);
    }
  }

  async function handleLogin() {
    const username = $("acc").value.trim();
    const password = $("pwd").value.trim();
    const spinner = $("loginSpinner");
    const btn = $("loginBtn");

    spinner.style.display = "inline-block";
    btn.disabled = true;

    if (username !== cfg.hardcodedUsername || password !== cfg.hardcodedPassword) {
      loginErr.textContent = "Invalid username or password.";
      loginErr.style.display = "block";
      spinner.style.display = "none";
      btn.disabled = false;
      return;
    }

    loginErr.style.display = "none";

    await recordLoginEvent();
    await fetchAssignment();

    showCard("task");
    spinner.style.display = "none";
    btn.disabled = false;
  }

  async function handleApprove() {
    const spinner = $("approveSpinner");
    const btn = $("approveBtn");

    spinner.style.display = "inline-block";
    btn.disabled = true;

    await completeAssignment("done");

    showCard("done");
    spinner.style.display = "none";
    btn.disabled = false;
  }

  $("loginBtn").onclick = handleLogin;
  $("approveBtn").onclick = handleApprove;

  document.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && loginCard.style.display !== "none") {
      $("loginBtn").click();
    }
  });

  showCard("login");
})();
