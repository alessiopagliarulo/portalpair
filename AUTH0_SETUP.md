# Auth0 Setup for Portal Pair

To enable coach login with university email verification:

## 1. Create an Auth0 account
Go to [auth0.com](https://auth0.com) and sign up.

## 2. Create an Application
- Dashboard → Applications → Create Application
- Choose **Single Page Application**
- Name it "Portal Pair"

## 3. Configure URLs
In your Application settings:
- **Allowed Callback URLs:** `http://localhost:8080/dashboard.html`
- **Allowed Logout URLs:** `http://localhost:8080/index.html`
- **Allowed Web Origins:** `http://localhost:8080`

For production, add your production URLs.

## 4. Enable Email Verification
- Authentication → Database → Your database (Username-Password-Authentication)
- Enable **Require Email Verification** so users must confirm their email

## 5. Restrict to University Emails (optional)
To allow only `.edu` or university domains:
- Create a **Rule** in Auth0 Dashboard → Rules
- Add logic to check `user.email` ends with `.edu` (or your allowed domains)
- Reject login if not from allowed domain

## 6. Update Config
Edit `js/config.js` and add your values:
```js
window.AUTH0_CONFIG = {
  domain: 'YOUR_TENANT.us.auth0.com',  // From Application settings
  clientId: 'YOUR_CLIENT_ID'            // From Application settings
};
```

## 7. Run the app
```bash
npm start
```

Visit http://localhost:8080 — you'll see the Portal Pair landing page. Click Sign up to create an account. Auth0 will send a confirmation email; after verifying, coaches can log in and access the dashboard.
