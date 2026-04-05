---
inclusion: always
---

# Testing Guidelines

## Test Philosophy

Focus on practical, meaningful tests rather than maximizing coverage metrics. Write tests that validate real-world behavior and catch actual bugs.

## Integration Testing Priority

When testing code that interacts with external services:

- **Prefer real integration tests** over mocked tests when authentication credentials are available via environment variables
- **Never default to mocks** when real service calls fail - investigate the root cause first
- **Debug authentication failures** by checking:
  - Request/response format compatibility
  - Token validity and expiration
  - API endpoint correctness
  - Network connectivity issues
- **Report unresolved issues** to the user rather than masking them with mocks

## Test Quality Over Quantity

- Write tests that exercise critical paths and edge cases
- Avoid redundant tests that don't add meaningful validation
- Focus on tests that would catch regressions in production scenarios
- Keep tests maintainable and easy to understand

