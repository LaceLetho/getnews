#!/usr/bin/env python3
"""QA Script 2: Verify API guide link preserved and async workflow text intact."""
import sys

def main():
    with open("README.md") as f:
        content = f.read()

    all_pass = True

    # Check API guide link exists
    checks = [
        ("docs/AI_ANALYZE_API_GUIDE.md reference", "docs/AI_ANALYZE_API_GUIDE.md" in content),
        ("POST /analyze mentioned", "POST /analyze" in content),
        ("async workflow - poll", "轮询" in content),
        ("async workflow - result", "取结果" in content),
        ("202 Accepted", "202" in content and "Accepted" in content),
        ("job_id in response", "job_id" in content),
        ("Bearer auth", "Bearer" in content),
    ]

    for label, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  {status}: {label}")

    result = "PASS" if all_pass else "FAIL"
    with open(".sisyphus/evidence/task-2-api-guide-link.txt", "w") as f:
        f.write(result + "\n")
    print(f"\nOverall: {result}")
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
