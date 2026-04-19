# Keystrokes-Dynamic

## Non-Technical User Manual

### Official Release Document

Prepared for: End Users, Operators, and Administrators  
Classification: Internal Use  
Owner: Keystrokes-Dynamic Project Team

---

## Cover Information

| Item | Details |
|---|---|
| Document title | Keystrokes-Dynamic Non-Technical User Manual |
| Document ID | KSD-UM-NT-001 |
| Version | 1.2 |
| Effective date | 12 April 2026 |
| Language | English |
| Owner | Keystrokes-Dynamic Project Team |
| Next review date | 12 October 2026 |

---

## Confidentiality Notice

This document is intended for internal operational use.
Do not distribute outside authorized teams without approval from the document owner.

---

## Document Control Matrix

| Control Item | Value |
|---|---|
| Classification | Internal Use |
| Document owner | Keystrokes-Dynamic Project Team |
| Review cycle | Every 6 months |
| Distribution authority | Project Owner / System Administrator |
| Master copy location | docs/MANUAL_BOOK_NON_TECHNICAL.md |
| Export copies | DOCX and PDF (generated from master) |

---

## Revision History

| Version | Date | Summary of Changes | Author |
|---|---|---|---|
| 1.0 | 11 April 2026 | Initial non-technical manual release | Project Team |
| 1.1 | 12 April 2026 | Added official format sections and stakeholder-ready structure | Project Team |
| 1.2 | 12 April 2026 | Added formal cover table, control matrix, revision table, and signature matrix | Project Team |

---

## Approval and Sign-Off

| Role | Name | Signature | Date |
|---|---|---|---|
| Prepared By | ________________________ | ________________________ | ________________________ |
| Reviewed By | ________________________ | ________________________ | ________________________ |
| Approved By | ________________________ | ________________________ | ________________________ |

---

## Distribution List

| Recipient Group | Controlled Copy |
|---|---|
| End User Support Team | Digital |
| System Administrator Team | Digital |
| Project Management Team | Digital |
| Research/Dataset Operations Team (if applicable) | Digital |

---

## How to Use This Manual

Read this document in order for first-time onboarding.

For quick issue handling:
- Use Section 10 (Common Errors and Fast Fixes)
- Use Section 13 (Support Checklist)

For admin operations:
- Use Section 9 (Admin Quick Guide)

---

[[PAGE_BREAK]]

## 1. What This Guide Is For

This guide is for everyday users, operators, and admins who are not technical.

You can use this manual to:
- Create and verify user accounts
- Log in safely with typing pattern verification
- Use two-factor verification if enabled
- Reset password when needed
- Collect dataset samples (if your role includes data collection)
- Handle common errors quickly

---

## 2. What This System Does

Keystrokes-Dynamic protects account login using two checks:
1. Your password
2. Your typing pattern (how you type)

Even if someone knows your password, they may still fail login if their typing pattern does not match yours.

---

## 3. Before You Start

Please prepare:
- A stable keyboard (preferably the one you usually use)
- A stable internet connection
- Your email inbox (for verification and reset code)

Best practice:
- Type naturally, not too fast and not too slow
- Use the same typing habit during registration and login
- Avoid switching keyboard device too often

---

## 4. First-Time User Steps

### Step 1: Open the Website

Open your system URL in browser.

For local testing (if instructed by your team):
- http://127.0.0.1:5000

### Step 2: Register

1. Open Register page
2. Enter username and password
3. Type your password sample as requested
4. Repeat until enrollment progress reaches required target

Important:
- The system stores timing behavior, not just text.
- Try to type consistently each sample.

### Step 3: Verify Your Email

1. Check your email inbox
2. Open the verification message
3. Enter the code/token in verification page
4. Wait for success message

If code expired:
- Use resend verification option

---

## 5. Daily Login Steps

1. Open Login page
2. Enter username and password
3. Type naturally in typing capture field
4. Submit login

Possible outcomes:
- Success: You enter dashboard
- Failed password: Wrong password text
- Failed biometric: Password correct but typing pattern mismatch

Tips when biometric fails:
- Slow down a bit
- Keep rhythm similar to registration
- Use the same keyboard/device if possible

---

## 6. If Two-Factor Verification Is Enabled

Some users will be asked for a second code after password+typing pass.

Flow:
1. Login normally
2. System asks for 2FA token
3. Enter token from authenticator app
4. Continue to dashboard

If 2FA token fails:
- Check phone time sync
- Wait for next token cycle and retry

---

## 7. Password Reset (User)

Use this if you cannot log in.

1. Open password reset flow
2. Request reset verification code
3. Check your email and verify reset code
4. Enter new password by typing it in capture field
5. Submit

Notes:
- New password also needs typing consistency for future login.
- After reset, re-enrollment samples may be required depending on progress state.

---

## 8. Dataset Collection Flow (For Research/Collection Team)

If you are assigned as dataset participant/operator:

### Register dataset subject
1. Open dataset page
2. Enter required identity fields
3. Set the password for collection
4. Save and receive subject code

### Submit typing samples
1. Use subject code
2. Type the same registered password
3. Submit samples repeatedly until target reached

Important:
- Session token is required by the system for secure submission.
- If token error appears, refresh page and restart session.

---

## 9. Admin Quick Guide

### Admin login
1. Open admin login page
2. Enter admin credentials
3. Access admin dashboard

### Admin common actions
- Review users
- Send reset email to user
- Delete user (with caution)
- Check diagnostics
- Check migration health endpoint

Safety for admins:
- Never delete the last admin account
- Confirm target user before destructive actions
- Keep audit log review routine

---

## 10. Common Errors and Fast Fixes

### A. "Incorrect password"
Cause:
- Wrong password text
Fix:
- Re-enter carefully
- Use show password if available

### B. "Biometric verification failed"
Cause:
- Typing pattern differs from enrollment
Fix:
- Type in your normal rhythm
- Use same keyboard/device
- Retry calmly

### C. "Training started" or "Training in progress"
Cause:
- Your model is being prepared
Fix:
- Wait briefly and retry login

### D. "Email not verified"
Cause:
- Account email verification incomplete
Fix:
- Verify from inbox
- Resend verification if needed

### E. "Too many attempts"
Cause:
- Rate limit triggered
Fix:
- Wait and retry later
- Contact admin if urgent

### F. Dataset token invalid
Cause:
- Session token missing/expired
Fix:
- Refresh dataset page
- Restart dataset registration/session

---

## 11. Security and Privacy Tips for Users

Do:
- Use strong password
- Keep email account secure
- Log out on shared computers
- Report suspicious login failures

Do not:
- Share password or verification code
- Share 2FA token
- Copy reset links to untrusted chat groups

---

## 12. Best Practices for Better Login Success

- Type naturally and consistently
- Avoid extreme speed changes
- Avoid frequent keyboard switching
- Avoid typing while distracted

If your typing habit changes a lot over time:
- Ask admin for support and possible retraining flow

---

## 13. Support Checklist (Before Contacting Admin)

Prepare these details:
- Username
- Date/time of issue
- Device/browser used
- Exact error message shown
- Screenshot (if possible)

This helps support resolve your issue faster.

---

## 14. Simple Glossary

- Enrollment: Initial sample collection phase
- Biometric score: How close your current typing matches your profile
- Threshold: Minimum score required to pass
- 2FA: Second verification code after login
- Dataset: Research collection samples

---

## 15. Governance and Compliance Notes

- This manual is a user-facing operational document and should be reviewed every 6 months.
- Any workflow updates in authentication, reset, dataset, or admin operations must be reflected in this document.
- Version updates must be recorded in the Revision History section.

---

## 16. Final Notes

This system is designed to improve account security while keeping login simple.

If you experience repeated failures:
- Stay calm
- Retry with natural rhythm
- Contact admin with support checklist data

End of non-technical manual.
