#!/usr/bin/env python3
"""QA script: Verify interface contract mentions both ContentItem and RawIntelligenceItem."""

import ast
import sys

def check_interface_contract():
    """Check that data_source_interface.py documents both ContentItem and RawIntelligenceItem returns."""
    with open("crypto_news_analyzer/crawlers/data_source_interface.py") as f:
        content = f.read()

    # Check module docstring mentions both types
    module_doc = content.split('"""')[1] if '"""' in content else ""
    has_content_item = "ContentItem" in module_doc
    has_raw_intelligence = "RawIntelligenceItem" in module_doc

    # Check crawl method docstring
    crawl_start = content.find("def crawl(")
    if crawl_start == -1:
        return False, "crawl method not found"

    # Find the next triple-quoted string after crawl
    rest = content[crawl_start:]
    first_docstring_start = rest.find('"""')
    if first_docstring_start == -1:
        return False, "crawl docstring not found"
    first_docstring_end = rest.find('"""', first_docstring_start + 3)
    crawl_doc = rest[first_docstring_start:first_docstring_end + 3]

    crawl_mentions_content = "ContentItem" in crawl_doc
    crawl_mentions_raw = "RawIntelligenceItem" in crawl_doc or "RawIntelligence" in crawl_doc

    print(f"Module doc mentions ContentItem: {has_content_item}")
    print(f"Module doc mentions RawIntelligenceItem: {has_raw_intelligence}")
    print(f"crawl() doc mentions ContentItem: {crawl_mentions_content}")
    print(f"crawl() doc mentions RawIntelligenceItem/RawIntelligence: {crawl_mentions_raw}")

    # Check intelligence crawlers
    telegram_ok = check_intelligence_crawler(
        "crypto_news_analyzer/crawlers/telegram_intelligence_crawler.py"
    )
    v2ex_ok = check_intelligence_crawler(
        "crypto_news_analyzer/crawlers/v2ex_intelligence_crawler.py"
    )

    print(f"\ntelegram_intelligence_crawler crawl returns List[RawIntelligenceItem] or List[Any]: {telegram_ok}")
    print(f"v2ex_intelligence_crawler crawl returns List[RawIntelligenceItem] or List[Any]: {v2ex_ok}")

    all_good = (
        has_content_item and has_raw_intelligence and
        crawl_mentions_content and crawl_mentions_raw and
        telegram_ok and v2ex_ok
    )

    return all_good, "PASS" if all_good else "FAIL"


def check_intelligence_crawler(filepath):
    """Check that intelligence crawler has correct return type annotation."""
    with open(filepath) as f:
        content = f.read()

    # Look for crawl method and its return type
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "crawl":
            # Get the return annotation
            if node.returns:
                ann = ast.unparse(node.returns)
                # Accept List[RawIntelligenceItem], List[Any], Sequence[Any], etc.
                return "List[RawIntelligenceItem]" in ann or "List[Any]" in ann or "Sequence[Any]" in ann
    return False


if __name__ == "__main__":
    ok, result = check_interface_contract()
    print(f"\n{'='*50}")
    print(f"QA RESULT: {result}")
    print(f"{'='*50}")
    sys.exit(0 if ok else 1)