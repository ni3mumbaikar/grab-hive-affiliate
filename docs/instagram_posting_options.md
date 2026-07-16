# Decision Document: Instagram Posting Options (JIRA-15)

This document evaluates and compares the three primary methods for automating image postings to Instagram.

---

## 1. Option Comparison Matrix

| Criteria | 1. Meta Graph API (Official) | 2. Private API Libraries (e.g. `instagrapi`) | 3. Browser Automation (e.g. Playwright / Selenium) |
| :--- | :--- | :--- | :--- |
| **Official Support** | ✅ Fully Supported (Official API) | ❌ Unsupported (Uses private endpoints) | ❌ Unsupported (Violates ToS) |
| **Setup Overhead** | ⚠️ High (Meta developer account, FB page link, IG Business account, OAuth setup) | ✅ Very Low (Needs standard username/password) | ⚠️ Medium (Need to code flow and handle login pages) |
| **Session Persistence** | ✅ Permanent (Uses Long-Lived Access Tokens) | ⚠️ Moderate (Session cookies can expire or be invalidated) | ⚠️ Low (Frequent login requests, MFA checks, bot protection) |
| **Account Ban Risk** | 0% (Safe) | 🚨 High (Meta detects private API headers and flags/shadowbans accounts) | ⚠️ Medium-High (Cloud flare / login page bot detection can trigger verification loops) |
| **Features** | Media publishing (posts, reels, stories), insights, comments. | Full user features (direct messages, stories, reels, posts, feed parsing). | Any action a standard browser user can perform. |
| **Hosting Cost** | Free. | Free. | Requires higher RAM/CPU to run headless browser. |

---

## 2. Option Details & Analysis

### Option A: Meta Graph API (Recommended for Production)
The Meta Graph API is the only officially supported way to publish content. 
- **Mechanism**: Use the `Content Publishing API` for Instagram Business Accounts.
- **Workflow**:
  1. Create a Facebook App in Meta Developer Portal.
  2. Connect an Instagram Professional (Creator/Business) Account to a Facebook Page.
  3. Generate a Long-Lived Page Access Token.
  4. Publish: POST image to container, then POST container publish endpoint.
- **Pros**: 100% safe, no ban risk, highly reliable.
- **Cons**: Complex initial registration; requires an Instagram Professional account.

### Option B: Private API Wrapper (`instagrapi`)
A highly popular Python library that reverse-engineers the mobile app's private endpoints.
- **Mechanism**: Simulates requests originating from the Instagram Android/iOS app.
- **Pros**: Extremely simple python code (`cl.photo_upload(...)`), bypasses Facebook Page requirements, works with personal accounts.
- **Cons**: High likelihood of getting account flagged, suspended, or blocked unless strict request throttling and proxy rotation are used.

### Option C: Headless Browser Automation (Playwright / Selenium)
Controls a browser instance to log in to the Instagram web portal and upload files.
- **Mechanism**: Fills out login form, handles MFA, clicks upload buttons, inputs caption, and publishes.
- **Pros**: Direct control, bypasses private API endpoint signatures.
- **Cons**: Instagram regularly updates class names and button layouts, breaking selectors. Captchas and bot challenges make headless logins very fragile.

---

## 3. Decision Recommendation

> [!IMPORTANT]
> **Recommended Decision**
> 1. **Staging / Development**: Implement a pluggable client architecture using `InstagramPublisher`. Start with a stub/mock publisher for local development.
> 2. **Production Deployment**: Implement the **Meta Graph API** client for the actual posting due to its stability, ToS compliance, and zero ban risk.
> 3. **Fallback Plan**: If a Meta Developer Account setup is not feasible immediately, use `instagrapi` with high delay limits and dummy accounts to avoid risk to primary business profiles.
