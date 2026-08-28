# Microsoft Entra delegated OAuth setup

This application supports delegated OAuth only. A user completes Microsoft sign-in and consents to Graph permissions. Do not configure application permissions or client-credentials access for this project.

## Register the application

1. In Microsoft Entra admin center, open **App registrations** and create a registration.
2. Choose the supported account type that matches your tenant policy. Use a tenant-specific ID in the WebUI when access must remain in one tenant; use `common` only when your registration supports it.
3. Under **Authentication**, add a **Web** redirect URI:

   ```text
   https://YOUR-WEBUI-ORIGIN/api/accounts/oauth/callback
   ```

   Local development may use `http://localhost:8080/api/accounts/oauth/callback`.

4. Record the application (client) ID and directory (tenant) ID.
5. If tenant policy requires a confidential web client, create a short-lived client secret and store its value only in the account connection dialog. Never paste it into source, Compose, screenshots, or issues.

## Delegated Microsoft Graph permissions

Add delegated permissions only. The application requests the following current scopes; disable workloads or reduce permissions when they are unnecessary:

- `User.Read`
- `Mail.ReadWrite`
- `Calendars.ReadWrite`
- `Tasks.ReadWrite`
- `Files.ReadWrite`
- `Team.ReadBasic.All`
- `Group.Read.All`
- `Notes.Read`
- `offline_access`

Some tenants require administrator consent for selected scopes. Consent does not make an unauthorized workload acceptable; the operator remains responsible for tenant policy, data access, and Microsoft terms.

## Connect an account

1. Configure `PUBLIC_BASE_URL` before starting the OAuth flow when behind a proxy.
2. Sign in to the WebUI and select **Connect account**.
3. Enter a local label, client ID, tenant ID, and client secret only when required.
4. Complete Microsoft sign-in in the popup.
5. Test the connection, review the returned profile, and enable only the desired development workloads.

The backend signs OAuth state with a short expiry and binds it to the client, tenant, and exact WebUI origin. The callback removes the authorization code from browser history, sends it only to its exact opener origin, exchanges it once, and does not persist the code.

## Revocation

Delete the account in the WebUI to remove its encrypted local tokens and logs. Also revoke the application's consent/session from Entra or the user's account portal, then delete the app registration when it is no longer needed.
