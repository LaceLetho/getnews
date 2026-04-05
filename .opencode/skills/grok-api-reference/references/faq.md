# Grok API - Faq

**Sections:** 8

---

## Table of Contents

- developers/faq/accounts
- developers/faq/billing
- developers/faq/general
- developers/faq
- developers/faq/security
- developers/faq/team-management
- grok/faq
- grok/faq/team-management

---

===/developers/faq/accounts===
#### FAQ

# Accounts

## How do I create an account for the API?

You can create an account at https://accounts.x.ai, or https://console.x.ai. To link your X account automatically to
your xAI account, choose to sign up with X account.

You can create multiple accounts of different sign-in methods with the same email.

When you sign-up with a sign-in method and with the same email, we will prompt you whether you
want to create a new account, or link to the existing account. We will not be able to merge the
content, subscriptions, etc. of different accounts.

## How do I update my xAI account email?

You can visit [xAI Accounts](https://accounts.x.ai). On the Account page, you can update your email.

## How do I add other sign-in methods?

Once you have signed-up for an account, you can add additional sign-in methods by going to [xAI Accounts](https://accounts.x.ai).

## I've forgotten my Multi-Factor Authentication (MFA) method, can you remove it?

You can generate your recovery codes at [xAI Accounts](https://accounts.x.ai) Security page.

We can't remove or reset your MFA method unless you have recovery codes due to security considerations. Please reach out to support@x.ai if you would like to delete the account instead.

## If I already have an account for Grok, can I use the same account for API access?

Yes, the account is shared between Grok and xAI API. You can manage the sign-in details at https://accounts.x.ai.

However, the billing is separate for Grok and xAI API. You can manage your billing for xAI API on [xAI Console](https://console.x.ai).
To manage billing for Grok, visit https://grok.com -> Settings -> Billing, or directly with Apple/Google if you made the
purchase via Apple App Store or Google Play.

## How do I manage my account?

You can visit [xAI Accounts](https://accounts.x.ai) to manage your account.

Please note the xAI account is different from the X account, and xAI cannot assist you with X account issues. Please
contact X via [X Help Center](https://help.x.com/) or Premium Support if you encounters any issues with your X account.

## I received an email of someone logging into my xAI account

xAI will send an email to you when someone logs into your xAI account. The login location is an approximation based on your IP address, which is dependent on your network setup and ISP and might not reflect exactly where the login happened.

If you think the login is not you, please [reset your password](https://accounts.x.ai/request-reset-password) and [clear your login sessions](https://accounts.x.ai/sessions). We also recommend all users to [add a multi-factor authentication method](https://accounts.x.ai/security).

## How do I delete my xAI account?

We are sorry to see you go!

You can visit [xAI Accounts](https://accounts.x.ai/account) to delete your account. You can restore your account after log in again and confirming restoration within 30 days.

You can cancel the deletion within 30 days by logging in again to any xAI websites and follow the prompt to confirm restoring the account.

For privacy requests, please go to: https://privacy.x.ai.

===/developers/faq/billing===
#### FAQ

# Billing

## I'm having payment issues with an Indian payment card

Unfortunately we cannot process Indian payment cards for our API service. We are working toward supporting it but you might want to consider using a third-party API in the meantime. As Grok Website and Apps' payments are handled differently, those are not affected.

## When will I be charged?

* Prepaid Credits: If you choose to use prepaid credits, you’ll be charged when you buy them. These credits will be assigned to the team you select during purchase.

* Monthly Invoiced Billing: If you set your [invoiced spending limit](/console/billing#monthly-invoiced-billing-and-invoiced-billing-limit) above $0, any usage beyond your prepaid credits will be charged at the end of the month.

* API Usage: When you make API requests, the cost is calculated immediately. The amount is either deducted from your available prepaid credits or added to your monthly invoice if credits are exhausted.

If you change your [invoiced spending limit](/console/billing#monthly-invoiced-billing-and-invoiced-billing-limit) to be greater than $0, you will be charged at the end of the month for any extra consumption after your prepaid credit on the team has run out.

Your API consumption will be calculated when making the requests, and the corresponding amount will be deducted from your remaining credits or added to your monthly invoice.

Check out [Billing](/console/billing) for more information.

## Can you retroactively generate an invoice with new billing information?

We are unable to retroactively generate an invoice. Please ensure your billing information is correct on [xAI Console](https://console.x.ai) Billing -> Payment.

## Can prepaid API credits be refunded?

Unfortunately, we are not able to offer refunds on any prepaid credit purchase unless in regions required by law. For details, please visit https://x.ai/legal/terms-of-service-enterprise.

### My prompt token consumption from the API is different from the token count I get from xAI Console Tokenizer or tokenize text endpoint

The inference endpoints add pre-defined tokens to help us process the request. Therefore, these tokens would be added to the total prompt token consumption. For more information, see:
[Estimating consumption with tokenizer on xAI Console or Estimating consumption with tokenizer on xAI Console or through API](/developers/rate-limits#estimating-consumption-with-tokenizer-on-xai-console-or-through-api).

===/developers/faq/general===
#### FAQ

# Frequently Asked Questions - General

Frequently asked questions by our customers.

For product-specific questions, visit  or .

### Does the xAI API provide access to live data?

Yes! With the agentic server-side [Web Search](/developers/tools/web-search) and [X Search](/developers/tools/x-search) tools.

### How do I contact Sales?

For customers with bespoke needs or to request custom pricing, please fill out our [Grok for Business form](https://x.ai/grok/business). A member of our team will reach out with next steps. You can also email us at [sales@x.ai](mailto:sales@x.ai).

### Where are your Terms of Service and Privacy Policy?

Please refer to our [Legal Resources](https://x.ai/legal) for our Enterprise Terms of Service and Data Processing Addendum.

### Does xAI sell crypto tokens?

xAI is not affiliated with any cryptocurrency. We are aware of several scam websites that unlawfully use our name and logo.

===/developers/faq===
#### Resources

# FAQ - xAI Console

Frequently asked questions on using the [xAI Console](https://console.x.ai), including creating teams, managing roles, and configuring settings.

You can find details on the following topics:

===/developers/faq/security===
#### FAQ

# Security

## Does xAI train on customers' API requests?

xAI never trains on your API inputs or outputs without your explicit permission.

API requests and responses are temporarily stored on our servers for 30 days in case they need to be audited for potential abuse or misuse. This data is automatically deleted after 30 days.

## Is the xAI API HIPAA compliant?

To inquire about a Business Associate Agreement (BAA), please complete our [BAA Questionnaire](https://forms.gle/YAEdX3XUp6MvdEXW9). A member of our team will review your responses and reach out with next steps.

## Is xAI GDPR and SOC II compliant?

We are SOC 2 Type 2 compliant. Customers with a signed NDA can refer to our [Trust Center](https://trust.x.ai/) for up-to-date information on our certifications and data governance.

## Do you have Audit Logs?

Team admins are able to view an audit log of user interactions. This lists all of the user interactions with our API server. You can view it at [xAI Console -> Audit Log](https://console.x.ai/team/default/audit).

The admin can also search by Event ID, Description or User to filter the results shown. For example, this is to filter by description matching `ListApiKeys`:

You can also view the audit log across a range of dates with the time filter:

## How can I securely manage my API keys?

Treat your xAI API keys as sensitive information, like passwords or credit card details. Do not share keys between teammates to avoid unauthorized access. Store keys securely using environment variables or secret management tools. Avoid committing keys to public repositories or source code.

Rotate keys regularly for added security. If you suspect a compromise, log into the xAI console first. Ensure you are viewing the correct team, as API keys are tied to specific teams. Navigate to the "API Keys" section via the sidebar. In the API Keys table, click the vertical ellipsis (three dots) next to the key. Select "Disable key" to deactivate it temporarily or "Delete key" to remove it permanently. Then, click the "Create API Key" button to generate a new one and update your applications.

xAI partners with GitHub's Secret Scanning program to detect leaked keys. If a leak is found, we disable the key and notify you via email. Monitor your account for unusual activity to stay protected.

===/developers/faq/team-management===
#### FAQ

# Team Management

## What are teams?

Teams are the level at which xAI tracks API usage, processes billing, and issues invoices.

* If you’re the team creator and don’t need a new team, you can rename your Personal Team and add members instead of creating a new one.
* Each team has **roles**:
  * **Admin**: Can modify team name, billing details, and manage members.
  * **Member**: Cannot make these changes.
  * The team creator is automatically an Admin.

## Which team am I on?

When you sign up for xAI, you’re automatically assigned to a **Personal Team**, which you can view the top bar of [xAI Console](https://console.x.ai).

## How can I manage teams and team members?

### Create a Team

1. Click the dropdown menu in the xAI Console.
2. Select **+ Create Team**.
3. Follow the on-screen instructions. You can edit these details later.

### Rename or Describe a Team

Admins can update the team name and description on the [Settings page](https://console.x.ai/team/default/settings).

### Manage Team Members

Admins can add or remove members by email on the [Users page](https://console.x.ai/team/default/users).

* Assign members as **Admin** or **Member**.
* If a user is removed, their API keys remain with the team.

### Delete a Team

Deleting a team removes its prepaid credits.

To permanently delete a team:

1. Go to the [Settings page](https://console.x.ai/team/default/settings).
2. Follow the instructions under **Delete Team**.

## How to automatically add users to team with my organization's email domain?

Admins can enable automatic team joining for users with a shared email domain:

1. Go to the [Settings page](https://console.x.ai/team/default/settings).
2. Add the domain under **Verified Domains**.
3. Add a `domain-verification` key to your domain’s DNS TXT record to verify ownership.

Users signing up with a verified domain email will automatically join the team.

===/grok/faq===
#### FAQ

# FAQ - Grok Website / Apps

While the documentation is mainly meant for our API users, you can find some commonly asked questions here for our consumer-facing website/apps.

## How can I link my X account sign-in/subscription to my xAI account?

On [Grok Website](https://grok.com), go to Settings -> Account. Click on Connect your X Account button. This will take you to X's SSO page to add X account as a sign-in method for xAI.

xAI will be able to retrieve your X subscription status and grant relevant benefits after linking.

You can manage your sign-in methods at https://accounts.x.ai.

## How do I add/remove other sign-in methods or link my X subscription?

You can add/remove your sign-in methods at https://accounts.x.ai. Your account must have at least one sign-in method.

Linking or signing up with X account will automatically link your X account subscription status with xAI, which can be used on https://grok.com.

## I signed-up to Grok / xAI API with my X account, why is xAI still asking for my email?

When you sign up with X, you will be prompted with the following:

As X does not provide the email address, you can have different emails on your X account and xAI account.

## I have issues using X, can I reach out to xAI for help?

While xAI provides the Grok in X service on X.com and X apps, it does not have operational oversight of X's service. You can contact X via their [Help Center](https://help.x.com/) or message [@premium on X](https://x.com/premium).

## How can I delete the account?

Your xAI account can be deleted by following the steps at [xAI Accounts](https://accounts.x.ai/account). If you are using the same account to access our API, your API access will be removed as well.

You can restore your account within 30 days by logging in again and confirming restoration.

## How do I unsubscribe?

If you have subscribed to SuperGrok, you can go to https://grok.com -> Settings -> Billing to manage your subscription (purchased from Grok Website), [Request a refund for app](https://support.apple.com/118223) (purchased from Apple App Store), or [Cancel, pause or change a subscription on Google Play](https://support.google.com/googleplay/answer/7018481) (purchased from Google Play).

If you have subscribed to X Premium, X (not xAI) would be responsible for processing refund where required by law. You can [submit a refund request from X](https://help.x.com/forms/x-refund-request). See more details regarding X Premium subscriptions on [X Help Center](https://help.x.com/using-x/x-premium).

===/grok/faq/team-management===
#### FAQ

# Team Management

## What are teams?

Teams are the level at which xAI tracks API usage, processes billing, and issues invoices.

* If you’re the team creator and don’t need a new team, you can rename your Personal Team and add members instead of creating a new one.
* Each team has **roles**:
  * **Admin**: Can modify team name, billing details, and manage members.
  * **Member**: Cannot make these changes.
  * The team creator is automatically an Admin.

## Which team am I on?

When you sign up for xAI, you’re automatically assigned to a **Personal Team**, which you can view the top bar of [xAI Console](https://console.x.ai).

## How can I manage teams and team members?

### Create a Team

1. Click the dropdown menu in the xAI Console.
2. Select **+ Create Team**.
3. Follow the on-screen instructions. You can edit these details later.

### Rename or Describe a Team

Admins can update the team name and description on the [Settings page](https://console.x.ai/team/default/settings).

### Manage Team Members

Admins can add or remove members by email on the [Users page](https://console.x.ai/team/default/users).

* Assign members as **Admin** or **Member**.
* If a user is removed, their API keys remain with the team.

### Delete a Team

Deleting a team removes its prepaid credits.

To permanently delete a team:

1. Go to the [Settings page](https://console.x.ai/team/default/settings).
2. Follow the instructions under **Delete Team**.

## How to automatically add users to team with my organization's email domain?

Admins can enable automatic team joining for users with a shared email domain:

1. Go to the [Settings page](https://console.x.ai/team/default/settings).
2. Add the domain under **Verified Domains**.
3. Add a `domain-verification` key to your domain’s DNS TXT record to verify ownership.

Users signing up with a verified domain email will automatically join the team.

