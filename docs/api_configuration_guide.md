# API & Configuration Guide (JIRA-38)

This guide provides detailed setup instructions for acquiring credentials for each external API integration.

---

## 1. Google Sheets API Configuration

### Step 1: Create a Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click **Select a project** (top left) -> **New Project**. Name it `GrabHive-Affiliate`.

### Step 2: Enable APIs
1. Search for and enable the **Google Sheets API**.
2. Search for and enable the **Google Drive API**.

### Step 3: Create Service Account Credentials
1. Navigate to **IAM & Admin** > **Service Accounts**.
2. Click **Create Service Account** at the top. Specify a name (e.g. `grabhive-sheet-editor`) and click **Create and Continue**.
3. Skip roles (or select Project > Editor if needed) and click **Done**.
4. In the Service Accounts list, click on your newly created service account.
5. Go to the **Keys** tab > **Add Key** > **Create new key**.
6. Select **JSON** format and click **Create**. A file (e.g., `keys.json`) will download automatically.
7. Save this file as `config/service_account.json` in your workspace, or copy its entire string content into your `.env` as `GOOGLE_SERVICE_ACCOUNT_JSON`.

### Step 4: Share Google Sheet with Service Account
1. Open the downloaded `keys.json` file and copy the `"client_email"` address (looks like `grabhive-sheet-editor@...iam.gserviceaccount.com`).
2. Open your target Google Sheet in your web browser.
3. Click the **Share** button (top right).
4. Paste the service account email, grant it **Editor** permissions, and click **Share**.
5. Copy the spreadsheet ID from the browser URL (the long character sequence between `/d/` and `/edit` in: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`). Paste this into your `.env` as `SPREADSHEET_ID`.

---

## 2. WhatsApp Cloud API Configuration

### Step 1: Set up Meta Developer Account
1. Go to the [Meta for Developers Portal](https://developers.facebook.com/).
2. Log in with your Facebook account and create a **Developer Account**.
3. Click **My Apps** > **Create App**. Select **Other** > **Business** type. Name it `GrabHive WhatsApp Bot`.

### Step 2: Add WhatsApp Product
1. On your App Dashboard, scroll down to **Add products to your app** and click **Set up** under **WhatsApp**.
2. Choose/Create a Meta Business Account and click **Continue**.

### Step 3: Retrieve Credentials
1. Under **WhatsApp** in the left menu, select **API Setup**.
2. Copy the **Temporary Access Token** (for production, configure a permanent System User Token in Meta Business Settings).
3. Copy the **Phone Number ID**.
4. Add a test phone number (e.g., your own phone number) to receive test messages.
5. In production, configure the token, phone number ID, and target WhatsApp Group ID or Chat ID in your `.env`.

---

## 3. Instagram Publishing Configuration

To automate posting to Instagram safely without account ban risks, use the **Meta Graph API**:

### Step 1: Convert Instagram Account to Professional
1. Open the Instagram app on your phone.
2. Go to **Settings** > **Account Type and Tools** > **Switch to Professional Account**.
3. Choose **Creator** or **Business**.

### Step 2: Link to a Facebook Page
1. Create a Facebook Page representing your brand/company.
2. Go to Page Settings > **Linked Accounts** > **Instagram**.
3. Click **Connect Account** and log in to authorize the link.

### Step 3: Get Page Access Token via Meta App
1. Go to your Meta Developer app dashboard.
2. Ensure you have added the **Instagram Graph API** product.
3. Use the **Graph API Explorer** tool to generate a **Page Access Token** with permissions:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
4. Exchange this token for a long-lived (60 days) or permanent token.
5. Copy the token and account credentials into `.env`.
