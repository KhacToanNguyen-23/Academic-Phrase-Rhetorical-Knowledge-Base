# Parallel Google and organization-email sign-in

The sign-in page offers two independent flows. Email and password accepts only
@hyperdatalab.org. Google sign-in accepts any verified Google account, and a new
Google account becomes a curator. Email registration validates the domain and adds
a curator account with a password of at least 8 characters, stored salted and hashed.
Email login requires the registered email and its password. There is no SMTP or
mailbox verification, so registration does not prove ownership of the mailbox.
Registration does not issue a session or navigate into the app. The user must sign in.
A curator created before passwords existed sets one by registering the same email again.

Google sign-in verifies Google's signed ID token, audience, expiry, verified email
and browser-bound nonce. The project's public OAuth client ID is the default in
`aprkb.core.config`; set GOOGLE_CLIENT_ID only to use a different client. Every origin
that serves the web app (http://127.0.0.1:5173, http://localhost:5173 and each deployed
URL) must be listed under Authorized JavaScript origins in Google Cloud.
An existing active curator email can also sign in through Google under the same account.

Admin API key setup happens once. Create the key with `make bootstrap-key`, open
"First-time admin setup", then enter the organization email, a password and the key
(or use Google).
The key is linked to that email or Google account, and later sign-ins do not need it.
A key that already has an email cannot be linked again. An email that was registered
as a curator cannot be linked to an admin key, so use an unregistered email.

Both login methods issue hashed server-side sessions that expire after eight hours.
Logout revokes the session. Refresh restores only a valid web session; it cannot use
a service API key or demo login. Quick demo and keyless local API access are disabled.

Run `uv run --directory apps/backend alembic upgrade head` before starting the backend.
