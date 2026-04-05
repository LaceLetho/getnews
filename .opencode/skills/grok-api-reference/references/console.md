# Grok API - Console

**Sections:** 6

---

## Table of Contents

- console/billing
- console/collections
- console/faq/accounts
- console/faq/billing
- console/faq/security
- console/usage

---

===/console/billing===
#### Key Information

# Manage Billing

**Ensure you are in the desired team before changing billing information. When you save the billing information or make a purchase for the first time, the billing information is saved to the team you are in and shared with its members.**

There are two ways of billing:

* **Prepaid credits:** You can pre-purchase credits for your team. Your API consumption will be deducted from remaining prepaid credits available.
* **Monthly invoiced billing:** xAI will generate a monthly invoice based on your API consumption, when you don't have available prepaid credits. xAI will charge your default payment method with the invoiced amount at the end of each month.

**Monthly invoiced billing is disabled by default, with default Invoiced Spending Limit of $0.** This will introduce service disruption when you have consumed all of your prepaid credits. To enable monthly invoiced billing, set a higher than $0 Invoiced Spending Limit at [Billing -> API Credits](https://console.x.ai/team/default/billing) on xAI Console.

Your API consumption will be accounted for in the following order:

* Free/Promotional credits
* Prepaid credits
* Monthly invoiced billing (if Invoiced Spending Limit > $0)

**Any prepaid credits and added payment method will be made available to the team you made the purchase in.**

## Prepaid credits



You can only purchase prepaid credits with Guest Checkout at the moment, due to regulatory
requirements.

This is the most common way to build with xAI API. Before using the API, you purchase a given amount of credits. When you use the API, xAI will track your consumption and deduct the amount from the credits available in your account.

You can add prepaid credits on the xAI Console [Billing -> API Credits](https://console.x.ai/team/default/billing) page.

On the same page, you can view the remaining prepaid credits, enter promo code, as well as any free credits granted by xAI team.

Note: When you make the purchase via bank transfer instead of credit card, the payment will take 2-3 business days to process. You will be granted credits after the process has completed.

## Monthly invoiced billing and invoiced billing limit

Enterprise customers might find it beneficial to enroll in monthly invoiced billing to avoid disruption to their services.

When you have set a **$0 invoiced billing limit** (default), xAI will only use your available prepaid credits. **Your API requests will be automatically rejected once your prepaid credits are depleted.**

If you want to use monthly billing, you can **increase your invoiced billing limit** on [Billing -> API Credits](https://console.x.ai/team/default/billing) page. xAI will attempt to use your prepaid credits first, and the remaining amount will be charged to your default payment method at the end of the month. This ensures you won't experience interruption while consuming the API.

Once your monthly invoiced billing amount has reached the invoiced billing limit, you won't be able to get response until you have raised the invoiced billing limit.

## Saving payment method

When you make a purchase, we automatically keep it on file to make your next purchase easier. You can also manually add payment method on xAI Console [Billing -> Billing details -> Add Payment Information](https://console.x.ai/team/default/billing).

Currently we don't allow user to remove the last payment method on file. There might be changes in the future.

## Invoices

You can view your invoices for prepaid credits and monthly invoices on [Billing -> Invoices](https://console.x.ai/team/default/billing/invoices).

## Billing address and tax information

Enter your billing information carefully, as it will appear on your invoices. We are not able to
regenerate the invoices at the moment.

Your billing address and tax information will be displayed on the invoice. On [Billing -> Payment](https://console.x.ai/team/default/billing), you can also add/change your billing address. When you add/change billing address, you can optionally add your organization's tax information.

===/console/collections===
#### Guides

# Using Collections in Console

This guide walks you through managing collections using the [xAI Console](https://console.x.ai) interface.

## Creating a new collection

Navigate to the **Collections** tab in the [xAI Console](https://console.x.ai). Make sure you are in the correct team.

Click on "Create new collection" to create a new `collection`.

You can choose to enable generate embeddings on document upload or not. We recommend leaving the generate embeddings setting to on.

## Viewing and editing collection configuration

You can view and edit the Collection's configuration by clicking on Edit Collection.

This opens up the following modal where you can view the configuration and make changes.

## Adding a document to the collection

Once you have created the new `collection`, you can click on it in the collections table to view the `documents` included in the `collection`.

Click on "Upload document" to upload a new `document`.

Once the upload has completed, each document is given a File ID. You can view the File ID, Collection ID and hash of the `document` by clicking on the `document` in the documents table.

## Deleting documents and collections

You can delete `documents` and `collections` by clicking on the more button on the right side of the collections or documents table.

===/console/faq/accounts===
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

===/console/faq/billing===
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

===/console/faq/security===
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

===/console/usage===
#### Key Information

# Usage Explorer

Sometimes as a team admin, you might want to monitor the API consumption, either to track spending, or to detect anomalies. xAI Console provides an easy-to-use [Usage Explorer](https://console.x.ai/team/default/usage) for team admins to track API usage across API keys, models, etc.

## Basic usage

[Usage Explorer](https://console.x.ai/team/default/usage) page provides intuitive dropdown menus for you to customize how you want to view the consumptions.

For example, you can view your daily credit consumption with `Granularity: Daily`:

By default, the usage is calculated by cost in USD. You can select Dimension -> Tokens or Dimension -> Billing items to change the dimension to token count or billing item count.

You can also see the usage with grouping. This way, you can easily compare the consumption across groups. In this case, we are trying to compare consumptions across test and production API keys, so we select `Group by: API Key`:

## Filters

The basic usage should suffice if you are only viewing general information. However, you can also use filters to conditionally display information.

The filters dropdown gives you the options to filter by a particular API key, a model, a request IP, a cluster, or the token type.

