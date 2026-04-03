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

    // If we cannot resolve either side, keep prior behavior.
    if (!currentBrand || !assignmentBrand) return true;
    return currentBrand === assignmentBrand;
  }

  function showCard(name) {
    loginCard.style.display = name === "login" ? "block" : "none";
    taskCard.style.display = name === "task" ? "block" : "none";
    doneCard.style.display = name === "done" ? "block" : "none";
  }

  function setFallbackDetails() {
    for (const field of cfg.fields) {
      const el = $(field.elementId);
      if (el) {
        el.textContent = cfg.fallbackDetails[field.key] || "";
      }
    }
  }

  function setTaskDetails(taskType) {
    const details = cfg.taskDetails[taskType] || cfg.fallbackDetails;
    for (const field of cfg.fields) {
      const el = $(field.elementId);
      if (el) {
        el.textContent = details[field.key] || "";
      }
    }
  }

  async function fetchCurrentAssignment() {
    try {
      const res = await fetch(`${API_BASE}/api/get-current-assignment`);
      const data = await res.json();

      if (!res.ok || !data.assignment) {
        setFallbackDetails();
        return;
      }

      const taskType = data.assignment.task_type || null;
      const assignmentSite = data.assignment.site_url || data.assignment.siteUrl || null;

      if (!isSameBrandTask(assignmentSite)) {
        setFallbackDetails();
        return;
      }

      setTaskDetails(taskType);
    } catch (err) {
      console.error("fetchCurrentAssignment failed:", err);
      localStorage.setItem("study_last_error", `fetchCurrentAssignment: ${String(err)}`);
      setFallbackDetails();
    }
  }

  async function recordLoginEvent() {
    try {
      await fetch(`${API_BASE}/api/record-login-event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ website: cfg.siteUrl }),
      });
    } catch (err) {
      console.error("recordLoginEvent failed:", err);
      localStorage.setItem("study_last_error", `recordLoginEvent: ${String(err)}`);
    }
  }

  async function completeAssignment(completionType) {
    try {
      await fetch(`${API_BASE}/api/record-complete-assignment-event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          website: cfg.siteUrl,
          completion_type: completionType,
        }),
      });
    } catch (err) {
      console.error("completeAssignment failed:", err);
      localStorage.setItem("study_last_error", `completeAssignment: ${String(err)}`);
    }
  }

  $("loginBtn").onclick = async () => {
    const username = $("acc").value.trim();
    const password = $("pwd").value.trim();
    const spinner = $("loginSpinner");
    const btn = $("loginBtn");

    spinner.style.display = "inline-block";
    btn.disabled = true;

    setTimeout(async () => {
      if (
        username === cfg.hardcodedUsername &&
        password === cfg.hardcodedPassword
      ) {
        loginErr.style.display = "none";
        showCard("task");
        await recordLoginEvent();
        await fetchCurrentAssignment();
      } else {
        loginErr.textContent = "Invalid username or password.";
        loginErr.style.display = "block";
      }

      spinner.style.display = "none";
      btn.disabled = false;
    }, 500);
  };

  $("approveBtn").onclick = async () => {
    const spinner = $("approveSpinner");
    const btn = $("approveBtn");

    spinner.style.display = "inline-block";
    btn.disabled = true;

    setTimeout(async () => {
      await completeAssignment("done");
      showCard("done");
      spinner.style.display = "none";
      btn.disabled = false;
    }, 800);
  };

  document.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && loginCard.style.display !== "none") {
      $("loginBtn").click();
    }
  });

  showCard("login");
})();