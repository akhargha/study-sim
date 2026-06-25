# Overview

This repository contains the backend server code and supporting infrastructure for the **MobyPhish** user study.

It includes:

* Backend server code
* Simulated phishing websites
* Deployment scripts
* SSL certificates
* Nginx configuration

---

# Website Files

The simulated websites are located in:

```text
apps/sites/
```

Each website has its own directory containing:

* `index.html`
* `favicon.*`

Be **very careful** when modifying or adding websites. Many site names differ by only a few characters, making it easy to introduce mistakes. Always thoroughly test any changes before deployment.

---

# Adding or Modifying Tasks

Each site's `index.html` contains a `taskDetails` variable that defines the tasks associated with that website.

If you add a new study task, you **must** update the corresponding site's `taskDetails` variable as well.

---

# Certificates

SSL certificates are stored in:

```text
certs/
```

The repository currently contains certificates for two certificate authorities:

* HappyTrust
* SadTrust

This directory is not particularly relevant for the current version of the study, since certificate phishing is not being tested.

---

# Hosting and Deployment

The websites are hosted on:

```text
gabriel@maple.cs.trincoll.edu
```

**Note:** This server is only accessible while connected to the Trinity College **eduroam** network.

The deployed websites live in:

```text
/var/www/study-sim/<site-name>
```

However, you should **not** edit files there directly.

Instead, make changes inside:

```text
apps/sites/
```

and deploy them using:

```bash
deploy/scripts/deploy_sites.sh
```

Before running the deployment script, review it to ensure it will perform the intended actions.

After deployment, reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

If you add a new website, make sure to:

1. Verify that the deployment scripts correctly generate the required Nginx configuration.
2. Add the appropriate domain alias and DNS mapping to the study laptop's `hosts` file, following the existing format.

---

# Backend Configuration

The backend code is located in:

```text
backend/
```

Most of the files are self-explanatory. The most important configuration file is:

```text
backend/.env
```

This file contains runtime configuration such as:

* `USER_ID`
* `SEND_TO_EMAIL`
* Database configuration
* Other environment-specific settings

If `.env` is missing, the backend falls back to:

```text
backend/config.py
```

**Important:** `config.py` is **only a fallback**. Do **not** modify it expecting production settings to change. In nearly all cases, configuration changes should be made in `.env`.

---

# Restarting the Backend

After making changes to the backend code or the `.env` file, restart the backend service:

```bash
sudo systemctl restart study-backend
```

---

# Python Virtual Environment

Before working on the backend, activate the project's virtual environment:

```bash
source venv/bin/activate
```

This ensures the correct Python packages and dependencies are available.
