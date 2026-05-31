# Problems

- Recipient-key collisions must be prevented across API and Telegram flows.
- Failed manual runs must not poison dedup history.
- Scheduled cache reads must not regress when recipient-scoped storage is added.
