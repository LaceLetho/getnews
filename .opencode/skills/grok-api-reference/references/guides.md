# Grok API - Guides

**Sections:** 4

---

## Table of Contents

- grok/apps/google-drive
- grok/management
- grok/organization
- grok/user-guide

---

===/grok/apps/google-drive===
#### Grok Business / Enterprise

# Google Drive Integration with Grok

## Overview: Connect Google Drive to Grok

Seamlessly search and reference your Google Drive files directly in Grok chats. This integration lets Grok access your team's shared files and your personal files to provide more accurate, grounded responses—reducing hallucinations and helping you work faster.

Powered by xAI's Collections API, the connector indexes files securely while respecting Google Drive permissions. Grok only retrieves content you can view. Files you don't have permission to view are never indexed or returned.

**Key benefits**:

* Get summaries, analyses, or answers with direct citations to your files.
* No need to manually upload or attach files. Grok searches automatically when relevant.
* Query files by content or metadata (filename, folder, owner, modification dates).

This feature is available in Grok Business and Enterprise plans. xAI doesn't use customer Google Drive data to train its models.

## Using Google Drive Files in Grok Chats

Once connected, Grok automatically searches relevant files—no extra steps needed.

**Examples of what to ask**:

* "Summarize the Q4 sales report from the Finance team documents."
* "What does our employee handbook say about remote work policies according to our company documents?"
* "Summarize my Go-to-market strategy document."

**Grok will**:

* Search content and metadata.
* Provide answers with inline citations linking back to the source file.
* Reason over multiple files when needed.

## Setting Up the Integration

Setup combines admin configuration for team shared files and optional user connections for personal files.

### Admin Setup: Enable for Shared Files

Team admins configure the connector once at the workspace level.

**Prerequisites**:

* You must be a Grok Business or Enterprise team admin.
* You must have purchased Grok Business or Enterprise licenses for your team.

**Steps**:

1. Log in to the xAI Console and go to **[Grok Business Apps](https://console.x.ai/team/default/grok-business/apps)**
2. Click **[Add to team](https://console.x.ai/team/default/grok-business/apps?add-connector-type=CONNECTOR_TYPE_GOOGLE_DRIVE)** for the Google Drive app.
3. Specify your Google Workspace domain.
4. Choose who can use the connector: everyone in the workspace or specific allowed users.
5. Sign in with your Google account and grant permissions. The OAuth authentication provides a secure way to allow access without sharing passwords.

Once connected, Grok immediately begins syncing files accessible to the admin's account. Shared files become available to authorized users right away.

Admins can later edit allowed users or remove the connector entirely from the same settings page.

### User Setup: Connect Your Personal Drive

End users can optionally connect their own Google Drive for searching their private files.

**Steps**:

1. On grok.com, go to **[Settings > Connected apps](https://grok.com/?_s=grok-business-connected-apps)**.
2. Select **Google Drive > Connect**.
3. Sign in with your Google account and grant permissions.
4. Your private files will sync and become searchable in your Grok chats.

To disconnect: Return to **[Settings > Connected apps](https://grok.com/?_s=grok-business-connected-apps)** and revoke access.

## Managing Your Integration

* Admins can view sync status and the list of users who have authenticated with Google Drive from **[Apps Settings page](https://console.x.ai/team/default/grok-business/apps)**.
* Admins or members can disconnect anytime to stop syncing their files.

## How Indexing and Syncing Works

* Initial sync starts immediately after admin setup.
* Ongoing: Grok checks for changes (new/updated/deleted files, permission changes) every hour.
* Permissions are always enforced. Grok only shows you files you can view in Google Drive.
* No inclusion/exclusion rules beyond the admin's initial access scope and user permissions.

**Supported file formats**:

Grok indexes a wide range of common file types from Google Drive, including native Google formats, Microsoft Office documents, PDFs, code files, and more.

| Category | File Formats |
|----------|--------------|
| Documents & Presentations | Google Docs, Sheets, and Slides, Microsoft Word (.doc, .docx), Microsoft Excel (.xls, .xlsx, including macro-enabled workbooks), Microsoft PowerPoint (.ppt, .pptx, including macro-enabled presentations and slideshows), Microsoft Outlook (.msg, .pst), PDFs, OpenDocument Text (.odt), Rich Text Format (.rtf), EPUB e-books |
| Data & Structured Files | CSV (comma-separated values), JSON, XML |
| Web & Markup | HTML, CSS, Markdown (.md) |
| Code Files | Python, JavaScript, TypeScript, C/C++ header and source files, SQL, YAML, TOML, Shell scripts, Ruby, Scala, Swift, Kotlin, Lua, PHP, Perl |
| Notebooks | Jupyter Notebooks (.ipynb), Google Colab notebooks |
| Email & Other | Email messages (.eml, RFC822 format), Plain text (.txt), TeXmacs |

## Limitations

* For files exceeding 128MB, Grok only indexes the first 128 MB of content.
* Sync checks hourly. Some recent changes may take up to an hour to appear.
* Only supported file types are indexed and are searchable (see list above)

## Frequently Asked Questions

**1. Why aren't my files appearing?**

Wait up to an hour for sync, or check permissions in Google Drive.

**2. Do I need to connect my personal Drive?**

No, shared files work via admin setup. Connect personal for your private files only.

**3. Can Grok edit files?**

No, read-only access for search and reference.

**4. How do I see which files were used?**

Grok includes citations in responses.

For troubleshooting or white-glove onboarding, please contact xAI support via .

===/grok/management===
#### Grok Business / Enterprise

# License & User Management

**The Grok Business overview page at [console.x.ai](https://console.x.ai) is your central hub for handling team licenses and user invitations.** As a team admin or user with appropriate permissions, you can buy licenses, invite new members, and manage access to ensure smooth collaboration.

Access this page by logging into [console.x.ai](https://console.x.ai) and navigating to the overview section. Note that actions like purchasing or provisioning require specific permissions—see the [Permissions](#permissions-and-troubleshooting) section for details.

## Purchasing Licenses

Expand your team's capabilities by buying additional licenses directly from the overview page.

Available license types:

* **SuperGrok:** Standard business access with enhanced quotas and features.
* **SuperGrok Heavy:** Upgraded performance for demanding workloads.

To purchase:

1. On the overview page, select the license type and quantity.
2. Enter payment details if prompted <em>(requires billing read-write permissions)</em>.
3. Confirm the purchase—licenses will be added to your available pool for assignment.

Purchased licenses become immediately available for provisioning to users.

&#x20;Ensure your team's billing is set up correctly to avoid
interruptions. Visit [Billing Settings](https://console.x.ai/team/default/billing) for more
details.

## Inviting Users

Invite new team members to join your Grok Business workspace with a simple email invitation process.

To invite:

1. On the overview page, click "Invite users to Grok Business".
2. Enter the users' email addresses.
3. Select a license type to auto-provision upon acceptance <em>(requires team read-write permissions)</em>.
4. Send the invitation—the user will receive an email with a link to activate their account.

Invited users gain access to the team workspace and basic team read permissions. (the latter is to allow for sharing conversations with your team members)

View invited users in the "Pending invitations" list on the overview page. As long as you have unassigned licenses available, they will be automatically provisioned when the user accepts.

## Assigning and Revoking Licenses

Once licenses are purchased or available, assign them to users for full team workspace access.

To assign:

1. From the overview page, select a user from your team list.
2. Choose an available license and assign it—access activates immediately.

To revoke:

1. Click the "..." for the user and choose "Unassign License" from the dropdown.
2. Confirm the action—the license returns to your available pool, and the user's will no longer have access to your team's workspace.

Revocations take effect instantly, so ensure that you communicate changes to affected users.

&#x20;Revoking a license removes team workspace access. Users will
retain personal workspace functionality.

## Canceling Licenses

Reduce your team's commitment by canceling unused licenses.

To cancel:

1. On the overview page, select the license type and quantity to cancel.
2. Submit the cancellation request <em>(requires billing read-write permissions)</em>.

Cancellations may take a few days to process, and eligible refunds will be issued to your billing method. Canceled licenses are removed from your pool once processed.

## Permissions and Troubleshooting

Most management actions require specific role-based permissions:

* **Billing Read-Write:** Needed to purchase or cancel licenses.
* **Team Read-Write:** Needed to invite users or assign/revoke licenses.

These are typically granted only to team admins. If you lack permissions:

* Contact your team admin to request actions like license assignment or purchases.
* Admins can adjust permissions via the overview page's role settings.

If you encounter issues, such as invitations not provisioning due to insufficient licenses, purchase more or revoke unused ones first.

&#x20;For white-glove support, Enterprise upgrades, or permission issues, contact xAI sales at .

===/grok/organization===
#### Grok Business / Enterprise

# Organization Management

**Organizations provide a higher-level governance structure for enterprise customers, encompassing multiple console teams under unified IT controls.** Available only to Enterprise tier subscribers, organizations enable centralized management of users, teams, and security features like SSO.

Access the organization dashboard by visiting [console.x.ai/organization](https://console.x.ai/organization). This page is restricted to organization admins.

&#x20;Organizations are exclusive to the Enterprise tier. Contact xAI
sales to upgrade if needed.

## Understanding Organizations

An organization acts as an overarching entity that groups related console teams, ideal for large enterprises with multiple business units or departments.

Key features:

* **Domain Association:** Link your organization to a specific email domain (e.g., @yourcompany.com). Any user signing up or logging in with an email from this domain is automatically associated with the organization.
* **User Visibility:** Organization admins can view a comprehensive list of all associated users across teams on the `/organization` page.
* **Team Association:** Teams created by organization members are automatically linked to the organization and displayed in the dashboard for oversight.

This structure supports a multi-team architecture, allowing independent Grok Business or API teams while maintaining centralized governance, such as uniform access controls and auditing.

## Viewing Users and Teams

To view users:

1. Navigate to [console.x.ai/organization](https://console.x.ai/organization).
2. Scroll to the "Users" section for a list of all domain-associated users, including their team affiliations and access status.

To view teams:

1. In the same dashboard, access the "Teams" section.
2. Review associated console teams, their members, and high-level usage metrics.

Use these views to ensure compliance, spot inactive accounts, or identify growth needs.

## Setting Up SSO

Secure and streamline logins by integrating Single Sign-On (SSO) with your preferred Identity Provider (IdP).

To configure SSO:

1. On the `/organization` page, click "Configure SSO".
2. Choose your IdP from the supported list (e.g., Okta, Azure AD, Google Workspace).
3. Follow the self-guided, IdP-specific instructions provided—each includes step-by-step setup, metadata exchange, and attribute mapping details.
4. Save your configuration and test SSO to confirm the functionality.

SSO setup is straightforward and tailored to common providers, ensuring quick deployment.

## Activating SSO and User Impact

Once configured, SSO will be activated and enforced organization-wide.

Post-activation:

* Users must log in via SSO on their next access.
* If a user selects "Log in with email" and enters a domain-associated address, (e.g., @yourcompany.com) the system automatically detects it and redirects to your IdP for authentication.
* Non-domain emails (e.g., @differentcompany.com) fall back to standard login methods.

This ensures seamless, secure access without disrupting workflows.

&#x20;Notify your users in advance about the SSO rollout to minimize
support queries.

## Setting up SCIM

Automate user provisioning and deprovisioning by integrating System for Cross-domain Identity Management (SCIM) with your Identity Provider (IdP). Follow these steps to set up SCIM effectively.

### Step 1: Configure Groups in Your IdP

1. On the `/organization` page, click "Setup SCIM".
2. Follow the IdP-specific steps provided to sync your groups.
3. Create as many groups as needed in your IdP—typically named something like `xai-admin`, `xai-supergrok-heavy`, `xai-supergrok`, or whatever fits your organizational structure.
   This step ensures your groups are ready for mapping and synchronization with xAI.

### Step 2: Map Groups to Roles in xAI

Map your IdP groups to the available roles in xAI.

* The out-of-the-box roles include Admin, SuperGrok Heavy, SuperGrok, and Member (the default role assigned to users without any specified group).
* If you require more granular roles beyond these, contact your xAI representative to explore custom setup options—these standard roles are usually sufficient for most organizations.
  This mapping aligns your IdP groups with xAI's role-based access controls.

### Step 3: Map Roles to Teams, Permissions, and Licenses

Assign your mapped roles to appropriate resources.

* Map roles to teams (usually just one primary team, but you may have more).
* Assign any relevant permissions.
* Typically, associate a license with the role.

This step customizes access and entitlements based on your organizational needs.

### Step 4: Preview and Activate SCIM

Before finalizing, review the changes.

* We provide a preview of what your organization will look like after activation.
* Confirm that members are assigned to the correct roles, those roles have the appropriate level of authorization, and the right licenses are applied.
* Once you feel confident everything is correct, click **"Activate"** to make SCIM your default provisioning system.

This verification ensures a smooth transition.

&#x20;SCIM is very disruptive. Users might lose or gain access to resources
they did not have before. Notify your organization that you are undergoing this transition and
**verify everything is correct during the preview stage before proceeding.**

## Need Help?

For assistance with organization setup, SSO troubleshooting, or Enterprise features, contact xAI sales at [x.ai/grok/business/enquire](https://x.ai/grok/business/enquire).

===/grok/user-guide===
#### Grok Business / Enterprise

# Grok.com User Guide

**Grok Business provides dedicated workspaces for personal and team use, with enhanced privacy and sharing controls.** Switch between workspaces to access team-specific features and ensure your conversations are protected under business plan terms.

A team workspace offers:

* Privacy guarantees as outlined in xAI's [terms of service](https://x.ai/legal/terms-of-service-enterprise).
* Full benefits of SuperGrok (or SuperGrok Heavy for upgraded licenses).
* Secure sharing of conversations limited to active team members.

## Workspaces Overview

Grok Business features two types of workspaces:

* **Personal Workspace:** For individual use, available unless disabled by your organization.
* **Team Workspace:** For collaborative work within your team, accessible only with an active license.

To switch between workspaces, use the workspace selector in the bottom left navigation on grok.com. Ensure you are in the correct workspace before starting new conversations.

&#x20;You can only access the team workspace when you have an
active license. If you lack access, contact your team admin.

## Privacy and Benefits

In your team workspace, enjoy enterprise-grade privacy protections as detailed in xAI's [terms of service](https://x.ai/legal/terms-of-service-enterprise). This includes data handling and, for the Enterprise tier, custom retention policies tailored for business use.

Additionally, unlock the full capabilities of SuperGrok, including higher usage quotas and advanced features. If your organization has an upgraded license, you may access SuperGrok Heavy for even more powerful performance.

Some users may not see a personal workspace. This indicates your organization has disabled
personal workspaces via an enterprise license. To enable or disable personal workspaces, reach out
to xAI sales for an Enterprise plan.

## Sharing Conversations

Sharing is restricted to your team for security:

* Share conversations only with team members who have active licenses.
* Share links are only accessible to licensed team members.
* If sent to non-team members or unlicensed team members, the link will not open.

To share a conversation:

1. Open the conversation in your team workspace.
2. Click the share button and select team members.
3. Generate and distribute the secure link.

View all shared conversations in your history at [https://grok.com/history?tab=shared-with-me](https://grok.com/history?tab=shared-with-me).

## Activating Your License

To activate or manage your license:

1. Visit your Grok Business overview at [console.x.ai](https://console.x.ai).
2. Press "Assign license" and select your license type.
3. If you encounter access issues or lack permissions, contact your team admin for assistance.

Once activated, your team workspace will become available on grok.com.

&#x20;For white-glove support and Enterprise features, contact xAI sales at .

