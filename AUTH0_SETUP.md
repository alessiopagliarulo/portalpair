# Auth0 Setup — 2FA Email Verification

Portal Pair uses Auth0 for 2-factor authentication: users enter a .edu email, receive a verification code, and sign in after entering the code.

## 1. Create an Auth0 Account

1. Go to **[auth0.com](https://auth0.com)** and sign up (free).
2. Create a **tenant** (e.g. `hackalytics-2026`).

## 2. Create an Application

1. In the Auth0 Dashboard, go to **Applications → Applications**.
2. Click **Create Application**.
3. Name it "Portal Pair".
4. Select **Regular Web Application** (needed for the Passwordless OTP flow).
5. Click **Create**.

## 3. Application Settings

1. Open your application → **Settings**.
2. Set **Allowed Callback URLs:**
   ```
   http://localhost:8080/dashboard.html
   ```
3. Set **Allowed Logout URLs:**
   ```
   http://localhost:8080/index.html
   ```
4. Scroll down to **Advanced Settings → Grant Types**.
5. Enable **Passwordless OTP**.
6. Click **Save Changes**.

## 4. Enable Passwordless Email (required — fixes "connection does not exist")

1. Go to **[Authentication → Passwordless](https://manage.auth0.com/#/connections/passwordless)**.
2. Turn **ON** the **Email** toggle (it must be enabled).
3. **Click on "Email"** to open the configuration panel (don’t stop after enabling the toggle).
4. Open the **Settings** tab:
   - **From**: Use an email that does **not** end in `auth0.com` (e.g. `noreply@yourdomain.com`). For testing, you can use a placeholder like `noreply@portalpair.com`; Auth0 will still try to send.
   - **Subject**: e.g. `Your verification code`
   - **Message**: Include `{{ code }}` for the OTP, e.g. `Your code is: {{ code }}`
5. Open the **Applications** tab and **enable** your Portal Pair application (so it can use this connection).
6. Click **Save**.
7. Wait 20–30 seconds for changes to apply.

## 5. Get Credentials

1. In **Applications → Your App → Settings**, copy:
   - **Domain** (e.g. `your-tenant.us.auth0.com`)
   - **Client ID**
   - **Client Secret**

## 6. Configure the App

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and set:
   ```
   AUTH0_DOMAIN=your-tenant.us.auth0.com
   AUTH0_CLIENT_ID=your_client_id
   AUTH0_CLIENT_SECRET=your_client_secret
   ```

## 7. Run

```bash
npm start
```

Open http://localhost:8080. Enter a .edu email, receive the code, enter it, and you’ll be redirected to the dashboard.

---

## Troubleshooting: "Connection does not exist"

This error means the Passwordless Email connection is not set up or not enabled for your app.

1. Go to [Authentication → Passwordless](https://manage.auth0.com/#/connections/passwordless).
2. Ensure **Email** is turned **ON**.
3. Click **Email** to open its config, then open the **Applications** tab and enable **Portal Pair** (your app).
4. Save and wait ~30 seconds, then try again.
