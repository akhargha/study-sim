# Study Sim Starter

This starter gives you:

- 9 static site directories
- 1 shared JavaScript file
- 1 shared stylesheet
- scripts to create HappyTrust and SadTrust root CAs
- a script to issue per-domain certificates
- a deploy script to sync the sites into `/var/www/study-sim`
- an Nginx server block template

## Important note about the CloudJet fake domain

Your fake domain written as `cIoudjetairways.com` uses a capital `I` in place of lowercase `l`.
DNS hostnames are case-insensitive, so browsers will normalize it to `cioudjetairways.com`.
That still works as a distinct domain, but the actual hostname to map in `/etc/hosts` should be `cioudjetairways.com`.

## Site behavior

All sites share the same logic in `apps/sites/shared/app.js`.

Each site has only:
- its own `index.html`
- its per-site config embedded into that file
- brand-specific color variables
- task-type-specific details

## Authentication

The current frontend is wired so the username must be the numeric `user_id`.
The page calls `/get-user-credentials` and compares the returned username/password against what the user entered.
That keeps the frontend simple while still using your `users` table.

## Local logs

If a network request fails, the frontend appends a local browser log to `localStorage`.
Key format:
- `study_logs_<siteUrl>`

## Next backend endpoints expected

- `POST /get-user-credentials`
- `POST /get-current-assignment`
- `POST /record-login-event`
- `POST /record-complete-assignment-event`
