# Local Email Verification Setup

Email verification is now working for local development! Here's how to use it:

## How It Works

The system now has a flexible email service that supports multiple backends:

- **Console Backend** (default): Emails are displayed in the Docker logs
- **File Backend**: Emails are saved to HTML files
- **SMTP Backend**: Send real emails via SMTP (Gmail, Outlook, etc.)

## Configuration

Your `.env` file has been configured with:

```bash
# Email Configuration (for local development)
EMAIL_BACKEND=console  # Options: console, file, smtp
EMAIL_FROM_ADDRESS=noreply@agentforge.local
EMAIL_FROM_NAME=AgentForge Development
FRONTEND_URL=http://localhost:3000
```

## Using Email Verification

### 1. Register a New User
When you register a new user, a verification email is automatically sent.

### 2. View the Email
Since we're using the `console` backend, the email appears in the Docker logs:

```bash
# View backend logs to see emails
docker compose logs backend -f
```

### 3. Get Verification Link
The email will show both HTML and text versions, including the verification link:
```
http://localhost:3000/verify-email?token=wH-8mT0Wj89x0T7sKp5KZd402H5MkweKqFNI8RjR-RY
```

### 4. Send Verification Email Manually
You can also request a new verification email:
- Go to your profile page (http://localhost:3000/profile)
- Click on "Email Verification" tab
- Click "Send Verification Email"

## Email Backends

### Console Backend (Current)
- **Best for**: Development and debugging
- **Config**: `EMAIL_BACKEND=console`
- **Where emails go**: Docker logs (visible with `docker compose logs backend`)

### File Backend
- **Best for**: Saving emails for review
- **Config**: 
  ```bash
  EMAIL_BACKEND=file
  EMAIL_FILE_DIR=tmp/emails  # optional
  ```
- **Where emails go**: HTML files in `tmp/emails/`

### SMTP Backend
- **Best for**: Testing with real email
- **Config**:
  ```bash
  EMAIL_BACKEND=smtp
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USERNAME=your-email@gmail.com
  SMTP_PASSWORD=your-app-password
  SMTP_USE_TLS=true
  ```
- **Where emails go**: Real email inboxes

## Testing the Current Setup

1. **Register a new user** (or use the existing test user):
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email": "test2@example.com", "username": "testuser2", "password": "TestPassword123!", "full_name": "Test User 2"}'
   ```

2. **Check Docker logs** to see the verification email:
   ```bash
   docker compose logs backend --tail=50
   ```

3. **Look for the email section** that starts with:
   ```
   📧 EMAIL SENT TO CONSOLE
   ================================================================================
   ```

4. **Copy the verification link** from the logs and paste it into your browser

5. **Verify the email** by visiting the link - it will redirect you to the verification page

## Switching to Real Email (Optional)

If you want to test with real emails, update your `.env` file:

```bash
# For Gmail (you'll need an app password)
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
EMAIL_FROM_ADDRESS=your-email@gmail.com
```

Then restart the backend:
```bash
docker compose restart backend
```

## Troubleshooting

### Email not appearing in logs?
1. Make sure `EMAIL_BACKEND=console` in your `.env`
2. Restart the backend: `docker compose restart backend`
3. Check logs: `docker compose logs backend -f`

### Verification link not working?
1. Make sure `FRONTEND_URL=http://localhost:3000` in your `.env`
2. Ensure the frontend is running on port 3000
3. Check that the token hasn't expired (24 hours)

### Want to see email files instead?
1. Change `EMAIL_BACKEND=file` in `.env`
2. Restart backend: `docker compose restart backend`
3. Check the `tmp/emails/` directory for HTML files

## Summary

✅ Email verification is now working locally!
✅ Emails display in console logs with full HTML/text content
✅ Users get verification emails when registering
✅ Manual "Send Verification Email" button works
✅ Both registration and manual verification flows are tested and working

You can now use the email verification feature just like in production, but with emails appearing in the development console instead of being sent to real email addresses.