#!/usr/bin/env python3
"""QA Script 1: Verify boundary docs contain required phrases."""
import sys

def check_file(path, required_phrases, label):
    with open(path) as f:
        content = f.read()
    results = []
    for phrase in required_phrases:
        found = phrase.lower() in content.lower()
        results.append((phrase, found))
        if not found:
            print(f"  FAIL [{label}]: missing phrase: {phrase}")
        else:
            print(f"  PASS [{label}]: found phrase: {phrase}")
    return all(r[1] for r in results)

def main():
    all_pass = True

    # README checks
    readme_phrases = [
        "dual-domain monorepo",
        "双域单体仓库",
        "intelligence/",
        "情报研究域",
        "同行域",
        "RawIntelligenceItem",
        "/intelligence/*",
        "/topic_*",
        "共享基础设施",
        "RSS/X/REST",
    ]
    if not check_file("README.md", readme_phrases, "README"):
        all_pass = False

    # ARCHITECTURE_BOUNDARIES checks
    boundary_phrases = [
        "Architecture Boundaries",
        "Dual-Domain Overview",
        "News Domain",
        "Intelligence Domain",
        "RSS/X/REST → ContentItem → LLMAnalyzer → ReportGenerator",
        "Telegram/V2EX → RawIntelligenceItem → TopicResearchScheduler → TopicFinding",
        "Shared Infrastructure",
        "PostgreSQL",
        "FastAPI",
        "Telegram",
        "Compatibility Contract",
        "Scope (This Refactor)",
        "Out of Scope",
        "no repo split",
        "no DB split",
        "no service split",
        "endpoint rename",
        "config format change",
        "dual-domain monorepo",
    ]
    if not check_file("docs/ARCHITECTURE_BOUNDARIES.md", boundary_phrases, "BOUNDARY"):
        all_pass = False

    # Write result
    result = "PASS" if all_pass else "FAIL"
    with open(".sisyphus/evidence/task-2-boundary-docs.txt", "w") as f:
        f.write(result + "\n")
    print(f"\nOverall: {result}")
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
