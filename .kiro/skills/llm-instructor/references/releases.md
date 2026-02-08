# Releases

Version history for this repository (106 releases).

## v1.14.5: v1.14.5
**Published:** 2026-01-29

## Changes

- fix(metadata): populate author field for PyPI stats

Separate author names from emails so hatchling populates the Author metadata field correctly. pypistats.org reads this field and was showing "None" because the names were only in author_email.

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/v1.14.5)

---

## v1.14.4: v1.14.4
**Published:** 2026-01-16

## What's Changed
* refactor(json_tracker): simplify using sibling heuristic by @thomasnormal in https://github.com/567-labs/instructor/pull/2000
* Responses API validation error by @jxnl in https://github.com/567-labs/instructor/pull/2002
* GenAI config labels loss by @jxnl in https://github.com/567-labs/instructor/pull/2005
* GenAI SafetySettings image content by @jxnl in https://github.com/567-labs/instructor/pull/2007
* List object crashes fix by @jxnl in https://github.com/567-labs/instructor/pull/2011
* New release preparation by @jxnl in https://github.com/567-labs/instructor/pull/2013


**Full Changelog**: https://github.com/567-labs/instructor/compare/v1.14.3...v1.14.4

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/v1.14.4)

---

## v1.14.3: v1.14.3
**Published:** 2026-01-13

## Added
- Completeness-based validation for Partial streaming - only validates JSON structures that are structurally complete (#1999)
- New `JsonCompleteness` class in `instructor/dsl/json_tracker.py` for tracking JSON completeness during streaming (#1999)

## Fixed
- Fixed Stream objects crashing reask handlers when using streaming with `max_retries > 1` (#1992)
- Field constraints (`min_length`, `max_length`, `ge`, `le`, etc.) now work correctly during streaming (#1999)

## Deprecated
- `PartialLiteralMixin` is now deprecated - completeness-based validation handles Literal/Enum types automatically (#1999)

**Full Changelog**: https://github.com/567-labs/instructor/compare/v1.14.2...v1.14.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/v1.14.3)

---

## v1.14.2: v1.14.2
**Published:** 2026-01-13

## Fixed
- Fixed model validators crashing during partial streaming by skipping them until streaming completes (#1994)
- Fixed infinite recursion with self-referential models in Partial (e.g., TreeNode with children: List["TreeNode"]) (#1997)

## Added
- Added `PartialLiteralMixin` documentation for handling Literal/Enum types during streaming (#1994)
- Added final validation against original model after streaming completes to enforce required fields (#1994)
- Added tests for recursive Partial models (#1997)

**Full Changelog**: https://github.com/567-labs/instructor/compare/v1.14.1...v1.14.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/v1.14.2)

---

## v1.14.1: v1.14.1
**Published:** 2026-01-08

## What's Changed
* fix(genai): Support cached_content for Google context caching by @b-antosik-marcura in https://github.com/567-labs/instructor/pull/1987

## New Contributors
* @b-antosik-marcura made their first contribution in https://github.com/567-labs/instructor/pull/1987

**Full Changelog**: https://github.com/567-labs/instructor/compare/v1.14.0...v1.14.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/v1.14.1)

---

## v1.14.0: v1.14.0
**Published:** 2026-01-08

## What's Changed
* Audit and standardize exception handling in instructor library by @jxnl in https://github.com/567-labs/instructor/pull/1897
* Standardize provider imports in documentation by @jxnl in https://github.com/567-labs/instructor/pull/1896
* Fix the issue by @jxnl in https://github.com/567-labs/instructor/pull/1914
* Standardize provider factory methods in codebase by @jxnl in https://github.com/567-labs/instructor/pull/1898
* Update image base URL in ipnb tutorials by @jxnl in https://github.com/567-labs/instructor/pull/1922
* docs: comprehensive documentation audit and SEO optimization by @jxnl in https://github.com/567-labs/instructor/pull/1944
* Update documentation for responses API mode by @jxnl in https://github.com/567-labs/instructor/pull/1946
* Doc / Removed model reference in client.create of extraction example. by @grokthetech-netizen in https://github.com/567-labs/instructor/pull/1951
* fix(auto_client): stop masking runtime ImportErrors in from_provider by @yurekami in https://github.com/567-labs/instructor/pull/1975
* fix: OpenAI provider in from_provider ignores base_url kwarg by @gardner in https://github.com/567-labs/instructor/pull/1971
* fix(genai): allow Union types for Google GenAI structured outputs by @majiayu000 in https://github.com/567-labs/instructor/pull/1973
* fix(genai): extract thinking_config and other fields from user-provided config object by @majiayu000 in https://github.com/567-labs/instructor/pull/1974
* fix(genai): extract thinking_config from user-provided config object by @majiayu000 in https://github.com/567-labs/instructor/pull/1972
* Fix typo in reask_validation.md by @mak2508 in https://github.com/567-labs/instructor/pull/1956
* Feature/bedrock document support by @lucagobbi in https://github.com/567-labs/instructor/pull/1936
* chore(typing): replace pyright with ty by @jxnl in https://github.com/567-labs/instructor/pull/1978
* Fix Cohere streaming and xAI tools validation by @jxnl in https://github.com/567-labs/instructor/pull/1983

## New Contributors
* @grokthetech-netizen made their first contribution in https://github.com/567-labs/instructor/pull/1951
* @yurekami made their first contribution in https://github.com/567-labs/instructor/pull/1975
* @gardner made their first contribution in https://github.com/567-labs/instructor/pull/1971
* @majiayu000 made their first contribution in https://github.com/567-labs/instructor/pull/1973
* @mak2508 made their first contribution in https://github.com/567-labs/instructor/pull/1956
* @lucagobbi made their first contribution in https://github.com/567-labs/instructor/pull/1936

**Full Changelog**: https://github.com/567-labs/instructor/compare/v1.13.0...v1.14.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/v1.14.0)

---

## v1.13.0: v1.13.0
**Published:** 2025-11-06

## What's Changed
* fix: Gemini HARM_CATEGORY_JAILBREAK and Anthropic tool_result blocks by @jxnl in https://github.com/567-labs/instructor/pull/1867
* fix(genai): fix Gemini streaming by @DaveOkpare in https://github.com/567-labs/instructor/pull/1864
* fix(processing): ensure JSON decode errors are caught by retry; add regression tests for JSON mode (#1856) by @devin-ai-integration[bot] in https://github.com/567-labs/instructor/pull/1857
* fix: resolve type checking diagnostics by @jxnl in https://github.com/567-labs/instructor/pull/1854
* fix: update openai dependency version constraints in pyproject.toml and uv.lock to support  v2 by @vishnu-itachi in https://github.com/567-labs/instructor/pull/1858
* feat: add py.typed marker for type checking by @jxnl in https://github.com/567-labs/instructor/pull/1868
* feat(Bedrock): add image support to Bedrock by @geekbass in https://github.com/567-labs/instructor/pull/1874
* chore(deps): bump the poetry group across 1 directory with 162 updates by @dependabot[bot] in https://github.com/567-labs/instructor/pull/1859
* Fix/ci uv migration by @jxnl in https://github.com/567-labs/instructor/pull/1886

## New Contributors
* @vishnu-itachi made their first contribution in https://github.com/567-labs/instructor/pull/1858
* @geekbass made their first contribution in https://github.com/567-labs/instructor/pull/1874

**Full Changelog**: https://github.com/567-labs/instructor/compare/v1.12.0...v1.13.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/v1.13.0)

---

## v1.12.0: v1.12.0
**Published:** 2025-10-27

## What's Changed
* feat: add mkdocs-llmstxt plugin and llms.txt support by @jxnl in https://github.com/567-labs/instructor/pull/1795
* Restore multimodal import compatibility by @jxnl in https://github.com/567-labs/instructor/pull/1797
* feat(retry): add comprehensive tracking of all failed attempts and exceptions by @jxnl in https://github.com/567-labs/instructor/pull/1802
* feat(hooks): add hook combination and per-call hooks support by @jxnl in https://github.com/567-labs/instructor/pull/1803
* feat(retry): propagate failed attempts through reask handlers by @jxnl in https://github.com/567-labs/instructor/pull/1804
* fix(responses): generalize tool call parsing for reasoning models by @sapountzis in https://github.com/567-labs/instructor/pull/1799
* feat(xai): add streaming support for xAI provider by @jeongyoonm in https://github.com/567-labs/instructor/pull/1758
* fix(openai): reask functionality broken in JSON mode since v1.9.0 by @pnkvalavala in https://github.com/567-labs/instructor/pull/1793
* fix(openai): remove duplicate schema from messages in JSON_SCHEMA mode by @pnkvalavala in https://github.com/567-labs/instructor/pull/1761
* Handle Anthropic tool_use retries on ValidationError by @kelvin-tran in https://github.com/567-labs/instructor/pull/1810
* Investigate instructor client import errors by @jxnl in https://github.com/567-labs/instructor/pull/1818
* fix: replace deprecated gpt-3.5-turbo-0613 with gpt-4o-mini by @sergiobayona in https://github.com/567-labs/instructor/pull/1830
* Update blog post link for LLM validation examples by @Mr-Ruben in https://github.com/567-labs/instructor/pull/1824
* Debug parse error hook not emitted by @jxnl in https://github.com/567-labs/instructor/pull/1819
* only use thinking_config in GenerateContentConfig by @jonbuffington in https://github.com/567-labs/instructor/pull/1751
* fix: Handle Gemini chunk.text ValueError when finish_reason=1 by @jxnl in https://github.com/567-labs/instructor/pull/1809
* docs: replace deprecated validation_context with context parameter by @devin-ai-integration[bot] in https://github.com/567-labs/instructor/pull/1831
* docs(validation): add context parameter examples and fix error output by @devin-ai-integration[bot] in https://github.com/567-labs/instructor/pull/1833
* also add pop thinking_config to handle_genai_tools by @oegedijk in https://github.com/567-labs/instructor/pull/1834
* update cohere text models. by @phlogisticfugu in https://github.com/567-labs/instructor/pull/1840
* fix(cohere): improve V2 API version detection and add documentation by @jxnl in https://github.com/567-labs/instructor/pull/1844
* doc(openrouter): use explicit async_client=False by @wongjiahau in https://github.com/567-labs/instructor/pull/1847
* Fix json parsing by @NicolasPllr1 in https://github.com/567-labs/instructor/pull/1836
* fix: Bedrock OpenAI models response parsing (reasoning before text) by @len-foss in https://github.com/567-labs/instructor/pull/1860
* fix: Python 3.13 compatibility and import path corrections by @jxnl in https://github.com/567-labs/instructor/pull/1866

## New Contributors
* @sapountzis made their first contribution in https://github.com/567-labs/instructor/pull/1799
* @jeongyoonm made their first contribution in https://github.com/567-labs/instructor/pull/1758
* @pnkvalavala made their first contribution in https://github.com/567-labs/instructor/pull/1793
* @kelvin-tran made their first contribution in https://github.com/567-labs/instructor/pull/1810
* @sergiobayona made their first contribution in https://github.com/567-labs/instructor/pull/1830
* @Mr-Ruben made their first contribution in https://github.com/567-labs/instructor/pull/1824
* @jonbuffington made their first contribution in https://github.com/567-labs/instructor/pull/1751
* @phlogisticfugu made their first contribution in https://github.com/567-labs/instructor/pull/1840
* @wongjiahau made their first contribution in https://github.com/567-labs/instructor/pull/1847
* @NicolasPllr1 made their first contribution in https://github.com/567-labs/instructor/pull/1836
* @len-foss made their first contribution in https://github.com/567-labs/instructor/pull/1860

**Full Changelog**: https://github.com/567-labs/instructor/compare/1.11.2...v1.12.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/v1.12.0)

---

## v1.11.3: v1.11.3
**Published:** 2025-09-09

## What's Changed
* feat: add mkdocs-llmstxt plugin and llms.txt support by @jxnl in https://github.com/567-labs/instructor/pull/1795
* Restore multimodal import compatibility by @jxnl in https://github.com/567-labs/instructor/pull/1797
* feat(retry): add comprehensive tracking of all failed attempts and exceptions by @jxnl in https://github.com/567-labs/instructor/pull/1802
* feat(hooks): add hook combination and per-call hooks support by @jxnl in https://github.com/567-labs/instructor/pull/1803


**Full Changelog**: https://github.com/567-labs/instructor/compare/1.11.2...v1.11.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/v1.11.3)

---

## 1.11.2: v1.11.2
**Published:** 2025-08-27

## What's Changed
* feat: Add automated bi-weekly scheduled releases by @jxnl in https://github.com/567-labs/instructor/pull/1787
* feat: Enhanced Google Cloud Storage Support for Multimodal Classes by @jxnl in https://github.com/567-labs/instructor/pull/1788
* Fix GCS URI Support for PDF and Audio Classes by @DaveOkpare in https://github.com/567-labs/instructor/pull/1763
* fix(exceptions): restore backwards compatibility for instructor.exceptions imports by @jxnl in https://github.com/567-labs/instructor/pull/1789


**Full Changelog**: https://github.com/567-labs/instructor/compare/v1.11.1...1.11.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.11.2)

---

## v1.11.0: v1.11.1
**Published:** 2025-08-27

## What's Changed
* fix(auto_client): add support for litellm provider in from_provider by @jxnl in https://github.com/567-labs/instructor/pull/1723
* refactor(utils): complete provider-specific utility reorganization by @jxnl in https://github.com/567-labs/instructor/pull/1722
* refactor: move provider-specific message conversion to handlers by @jxnl in https://github.com/567-labs/instructor/pull/1724
* Update contributing docs for provider utilities by @jxnl in https://github.com/567-labs/instructor/pull/1725
* Add consistent docstrings to utils modules by @jxnl in https://github.com/567-labs/instructor/pull/1726
* feat: add xAI utils pattern following standard provider structure by @jxnl in https://github.com/567-labs/instructor/pull/1728
* fix: implement missing hooks (completion:error and completion:last_attempt) by @jxnl in https://github.com/567-labs/instructor/pull/1729
* Reorganize codebase from flat structure to modular architecture by @jxnl in https://github.com/567-labs/instructor/pull/1730
* refactor: remove backward compatibility modules by @jxnl in https://github.com/567-labs/instructor/pull/1731
* feat: Add comprehensive tests for XAI _raw_response functionality by @devin-ai-integration[bot] in https://github.com/567-labs/instructor/pull/1735
* feat(batch): add in-memory batching support and improve error handling by @jxnl in https://github.com/567-labs/instructor/pull/1746
* chore: update author joschka website by @joschkabraun in https://github.com/567-labs/instructor/pull/1765
* fix(docs): correct broken tutorials navigation link by @cz3k in https://github.com/567-labs/instructor/pull/1768
* feat(docs): Truefoundry AI Gateway integration with Instructor by @rishiraj-tf in https://github.com/567-labs/instructor/pull/1767
* Fix Pydantic v2 deprecation warnings by migrating from class Config to   ConfigDict by @anistark in https://github.com/567-labs/instructor/pull/1782
* Add OpenRouter provider support to auto_client routing by @devin-ai-integration[bot] in https://github.com/567-labs/instructor/pull/1783

## New Contributors
* @cz3k made their first contribution in https://github.com/567-labs/instructor/pull/1768
* @rishiraj-tf made their first contribution in https://github.com/567-labs/instructor/pull/1767
* @anistark made their first contribution in https://github.com/567-labs/instructor/pull/1782

**Full Changelog**: https://github.com/567-labs/instructor/compare/1.10.0...v1.11.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/v1.11.0)

---

## 1.10.0: 1.10.0
**Published:** 2025-07-18

## What's Changed
* Update integrations to from_provider API by @jxnl in https://github.com/567-labs/instructor/pull/1668
* feat: Add native caching support with AutoCache and RedisCache adapters by @jxnl in https://github.com/567-labs/instructor/pull/1674
* feat: Enhance GitHub Actions workflow for testing by @jxnl in https://github.com/567-labs/instructor/pull/1675
* Deprecate google-generativeai in favor of google-genai by @jxnl in https://github.com/567-labs/instructor/pull/1673
* Fix batch request parsing by @jxnl in https://github.com/567-labs/instructor/pull/1677
* Enhance batch API with multi-provider support and improved CLI by @jxnl in https://github.com/567-labs/instructor/pull/1678
* split off dev dependencies by @hwong557 in https://github.com/567-labs/instructor/pull/1685
* Add Claude Code GitHub Workflow by @jxnl in https://github.com/567-labs/instructor/pull/1688
* fix(genai): handle response_model=None for GenAI modes by @jxnl in https://github.com/567-labs/instructor/pull/1694
* fix: correct is_simple_type logic for list types with BaseModel contents by @jxnl in https://github.com/567-labs/instructor/pull/1698
* fix(genai): add automatic Partial wrapping for streaming requests by @jxnl in https://github.com/567-labs/instructor/pull/1695
* fix(bedrock): add Bedrock-native format conversion to OpenAI format by @jxnl in https://github.com/567-labs/instructor/pull/1696
* fix(tests): improve prompt for UserExtract in gemini stream test by @jxnl in https://github.com/567-labs/instructor/pull/1700
* feat(bedrock): improve documentation and auto client support by @jxnl in https://github.com/567-labs/instructor/pull/1686
* chore(ci): run docs test monthly by @jxnl in https://github.com/567-labs/instructor/pull/1699
* Enhance logging and docs by @jxnl in https://github.com/567-labs/instructor/pull/1702
* chore: remove .vscode/settings.json from tracking by @jxnl in https://github.com/567-labs/instructor/pull/1705
* fix(genai): forward thinking_config parameter to Gemini models by @jxnl in https://github.com/567-labs/instructor/pull/1704
* Fix/decimal support genai by @jxnl in https://github.com/567-labs/instructor/pull/1712
* docs: update provider syntax by @jxnl in https://github.com/567-labs/instructor/pull/1713
* feat(provider): add deepseek support by @NasonZ in https://github.com/567-labs/instructor/pull/1715
* feat(auto_client): add comprehensive api_key parameter support for all providers by @johnwlockwood in https://github.com/567-labs/instructor/pull/1717
* Add Anthropic parallel tool support by @jxnl in https://github.com/567-labs/instructor/pull/1719

## New Contributors
* @hwong557 made their first contribution in https://github.com/567-labs/instructor/pull/1685
* @johnwlockwood made their first contribution in https://github.com/567-labs/instructor/pull/1717

**Full Changelog**: https://github.com/567-labs/instructor/compare/1.9.2...1.10.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.10.0)

---

## 1.9.2: 1.9.2
**Published:** 2025-07-07

## What's Changed
* Fix docs build path by @jxnl in https://github.com/567-labs/instructor/pull/1662
* Revert "refactor: simplify safety settings configuration for Gemini API" by @jxnl in https://github.com/567-labs/instructor/pull/1664
* Skip LLM tests without API keys by @jxnl in https://github.com/567-labs/instructor/pull/1665
* Add xAI provider by @jxnl in https://github.com/567-labs/instructor/pull/1661
* Fix GenAI image harm categories by @jxnl in https://github.com/567-labs/instructor/pull/1667


**Full Changelog**: https://github.com/567-labs/instructor/compare/1.9.1...1.9.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.9.2)

---

## 1.9.1: 1.9.1
**Published:** 2025-07-07

## What's Changed
* feat: add Azure OpenAI support to auto_client.py by @jxnl in https://github.com/567-labs/instructor/pull/1633
* fix: expose exception classes in public API by @ivanleomk in https://github.com/567-labs/instructor/pull/1613
* Update TaskAction method description for clarity on task creation and… by @eaedk in https://github.com/567-labs/instructor/pull/1637
* Fix SambaNova capitalization by @jxnl in https://github.com/567-labs/instructor/pull/1651
* refactor: simplify safety settings configuration for Gemini API by @DaveOkpare in https://github.com/567-labs/instructor/pull/1659
* Json schema fix by @Canttuchdiz in https://github.com/567-labs/instructor/pull/1657

## New Contributors
* @eaedk made their first contribution in https://github.com/567-labs/instructor/pull/1637
* @Canttuchdiz made their first contribution in https://github.com/567-labs/instructor/pull/1657

**Full Changelog**: https://github.com/567-labs/instructor/compare/1.9.0...1.9.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.9.1)

---

## 1.9.0: 1.9.0
**Published:** 2025-06-21

## What's Changed
* feat: Improve error handling with comprehensive exception hierarchy by @jxnl in https://github.com/567-labs/instructor/pull/1549
* Remove `enable_prompt_caching` from Anthropic integration since we ha… by @ivanleomk in https://github.com/567-labs/instructor/pull/1562
* Fix/docs by @ivanleomk in https://github.com/567-labs/instructor/pull/1561
* lock by @jxnl in https://github.com/567-labs/instructor/pull/1565
* Fix/gemini config by @ivanleomk in https://github.com/567-labs/instructor/pull/1563
* feat(deps): allow rich version 14+ by @devin-ai-integration in https://github.com/567-labs/instructor/pull/1566
* chore(deps): bump the poetry group across 1 directory with 26 updates by @dependabot in https://github.com/567-labs/instructor/pull/1569
* chore(deps): bump anthropic from 0.52.0 to 0.52.1 in the poetry group by @dependabot in https://github.com/567-labs/instructor/pull/1571
* Standardize async parameter naming in VertexAI client by @devin-ai-integration in https://github.com/567-labs/instructor/pull/1555
* Add Claude Code GitHub Workflow by @ivanleomk in https://github.com/567-labs/instructor/pull/1575
* feat: update README to reflect 3M monthly downloads milestone by @ivanleomk in https://github.com/567-labs/instructor/pull/1577
* fix(deps): add dev and docs to project.optional-dependencies for uv compatibility by @devin-ai-integration in https://github.com/567-labs/instructor/pull/1581
* docs: add Gemini thought parts filtering explanation to GenAI integration by @devin-ai-integration in https://github.com/567-labs/instructor/pull/1583
* fix: filter out Gemini thought parts in genai tool parsing by @indigoviolet in https://github.com/567-labs/instructor/pull/1578
* Fix documentation for dynamic model creation example by @devin-ai-integration in https://github.com/567-labs/instructor/pull/1567
* chore(deps): bump the poetry group across 1 directory with 11 updates by @dependabot in https://github.com/567-labs/instructor/pull/1595
* feat: implementation of JSON mode for Writer proider by @yanomaly in https://github.com/567-labs/instructor/pull/1559
* feat(auto_client): add Ollama provider support by @jxnl in https://github.com/567-labs/instructor/pull/1602
* fix: respect timeout parameter in retry mechanism for Ollama compatibility by @jxnl in https://github.com/567-labs/instructor/pull/1603
* fix(reask): handle ThinkingBlock in reask_anthropic_json by @jxnl in https://github.com/567-labs/instructor/pull/1604
* feat(docs): Add cross-links to blog posts for better navigation by @jxnl in https://github.com/567-labs/instructor/pull/1605
* docs: improve clarity and consistency across documentation by @jxnl in https://github.com/567-labs/instructor/pull/1606
* feat: Enable Audio module to work with Windows by @ish-codes-magic in https://github.com/567-labs/instructor/pull/1619
* fix(deps): relax tenacity requirement to support google-genai 1.21.1 by @jxnl in https://github.com/567-labs/instructor/pull/1625
* fix: resolve pyright TypedDict key access error in dump_message by @jxnl in https://github.com/567-labs/instructor/pull/1626
* feat(docs): improve SEO for asyncio and tenacity documentation by @jxnl in https://github.com/567-labs/instructor/pull/1620
* Resolve dependency version conflicts by @jxnl in https://github.com/567-labs/instructor/pull/1627
* Feat/add gemini optional support by @ivanleomk in https://github.com/567-labs/instructor/pull/1618

## New Contributors
* @ish-codes-magic made their first contribution in https://github.com/567-labs/instructor/pull/1619

**Full Changelog**: https://github.com/567-labs/instructor/compare/1.8.3...1.9.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.9.0)

---

## 1.8.3: 1.8.3
**Published:** 2025-05-22

## What's Changed
* docs: improve CLAUDE.md with better architecture description by @jxnl in https://github.com/567-labs/instructor/pull/1525
* fix(bedrock): minimal working example with from_bedrock client by @dogonthehorizon in https://github.com/567-labs/instructor/pull/1528
* docs(blog): fix code block formatting in blog post by @workwithpurwarkrishna in https://github.com/567-labs/instructor/pull/1526
* feat(bedrock): sort of add support for async bedrock client by @dogonthehorizon in https://github.com/567-labs/instructor/pull/1530
* fix(bedrock): handle default message format for converse endpoint by @dogonthehorizon in https://github.com/567-labs/instructor/pull/1529
* Add semantic validation documentation by @jxnl in https://github.com/567-labs/instructor/pull/1541
* Implementing support for responses by @ivanleomk in https://github.com/567-labs/instructor/pull/1520
* fix: remove failing test by @ivanleomk in https://github.com/567-labs/instructor/pull/1544
* fix: bump version by @ivanleomk in https://github.com/567-labs/instructor/pull/1545

## New Contributors
* @dogonthehorizon made their first contribution in https://github.com/567-labs/instructor/pull/1528
* @workwithpurwarkrishna made their first contribution in https://github.com/567-labs/instructor/pull/1526

**Full Changelog**: https://github.com/567-labs/instructor/compare/1.8.2...1.8.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.8.3)

---

## 1.8.2: 1.8.2
**Published:** 2025-05-15

## What's Changed
* fix: removed print statement by @ivanleomk in https://github.com/567-labs/instructor/pull/1524


**Full Changelog**: https://github.com/567-labs/instructor/compare/1.8.1...1.8.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.8.2)

---

## 1.8.1: 1.8.1
**Published:** 2025-05-09

## What's Changed
* docs(blog): add Anthropic web search structured data blog post by @jxnl in https://github.com/567-labs/instructor/pull/1515
* fix: added support for calling streaming from the create method by @ivanleomk in https://github.com/567-labs/instructor/pull/1502
* Fix/mkdocs by @ivanleomk in https://github.com/567-labs/instructor/pull/1517
* docs(blog): announce unified provider interface (from_provider) by @jxnl in https://github.com/567-labs/instructor/pull/1516
* Fix/anthropic web search by @ivanleomk in https://github.com/567-labs/instructor/pull/1519


**Full Changelog**: https://github.com/567-labs/instructor/compare/1.8.0...1.8.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.8.1)

---

## 1.8.0: 1.8.0
**Published:** 2025-05-07

## What's Changed
* Fix typo by @tdhopper in https://github.com/567-labs/instructor/pull/1468
* bunch of other typos in blog posts fixed by @0xRaduan in https://github.com/567-labs/instructor/pull/1477
* remove duplicate providers from integrations page by @0xRaduan in https://github.com/567-labs/instructor/pull/1475
* Fix typos in docs/tutorials/ directory by @0xRaduan in https://github.com/567-labs/instructor/pull/1474
* Simplify learning docs for new users by @jxnl in https://github.com/567-labs/instructor/pull/1479
* fix(google-genai): Add more helpful error messages by @stephen-iezzi in https://github.com/567-labs/instructor/pull/1484
* Fix is_simple_type function for list[int | str] in Python 3.10 by @paulelliotco in https://github.com/567-labs/instructor/pull/1458
* fix typo by @jss367 in https://github.com/567-labs/instructor/pull/1497
* Fix: simple test failure by @ivanleomk in https://github.com/567-labs/instructor/pull/1505
* Added a check for genai response  by @ivanleomk in https://github.com/567-labs/instructor/pull/1506
* Add unified provider interface with string-based initialization by @jxnl in https://github.com/567-labs/instructor/pull/1490

## New Contributors
* @tdhopper made their first contribution in https://github.com/567-labs/instructor/pull/1468
* @0xRaduan made their first contribution in https://github.com/567-labs/instructor/pull/1477
* @jss367 made their first contribution in https://github.com/567-labs/instructor/pull/1497

**Full Changelog**: https://github.com/567-labs/instructor/compare/1.7.9...1.8.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.8.0)

---

## 1.7.9: 1.7.9
**Published:** 2025-04-03

## What's Changed
* add async partial streaming support for genai by @oegedijk in https://github.com/instructor-ai/instructor/pull/1441
* Update from_litellm type hints to properly return AsyncInstructor by @jonchun in https://github.com/instructor-ai/instructor/pull/1324
* docs: add cookbook on tracing with Langfuse by @jannikmaierhoefer in https://github.com/instructor-ai/instructor/pull/1452
* Gemini Config Options Documentation by @fjooord in https://github.com/instructor-ai/instructor/pull/1455
* feat: add mistral PDF support by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1459
* Fix: resolve pyright issues with PDF by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1465

## New Contributors
* @oegedijk made their first contribution in https://github.com/instructor-ai/instructor/pull/1441
* @jonchun made their first contribution in https://github.com/instructor-ai/instructor/pull/1324
* @jannikmaierhoefer made their first contribution in https://github.com/instructor-ai/instructor/pull/1452

**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.7.8...1.7.9

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.7.9)

---

## 1.7.8: 1.7.8
**Published:** 2025-03-29

## What's Changed
* docs: Add Cursor rules documentation by @jxnl in https://github.com/instructor-ai/instructor/pull/1423
* docs: improve contributing guidelines with UV installation and conventional comments by @jxnl in https://github.com/instructor-ai/instructor/pull/1424
* docs: add LLM documentation and update mkdocs.yml with redirect by @jxnl in https://github.com/instructor-ai/instructor/pull/1425
* docs(github): update cursor rules with proper website link and multiline PR instructions by @jxnl in https://github.com/instructor-ai/instructor/pull/1427
* Adding Streaming for Mistral and VertexAI by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1420
* docs(blog): add post about Cursor rules for Git best practices by @jxnl in https://github.com/instructor-ai/instructor/pull/1430
* docs(blog): announce llms.txt implementation by @jxnl in https://github.com/instructor-ai/instructor/pull/1431
* chore: add pr_body.md to gitignore by @jxnl in https://github.com/instructor-ai/instructor/pull/1432
* docs: add OpenAI audio extraction example by @jxnl in https://github.com/instructor-ai/instructor/pull/1433
* feat: added new article by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1446
* Bugfix: [minor] Do not fail with google genai models if the content is longer then max file name. Closes #1439 by @sztanko in https://github.com/instructor-ai/instructor/pull/1440

## New Contributors
* @sztanko made their first contribution in https://github.com/instructor-ai/instructor/pull/1440

**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.7.7...1.7.8

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.7.8)

---

## 1.7.7: 1.7.7
**Published:** 2025-03-17

## What's Changed
* feat: adding sync and async example for sambanova by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1415
* fix: bump version + fix deps by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1417


**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.7.6...1.7.7

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.7.7)

---

## 1.7.6: 1.7.6
**Published:** 2025-03-17

## What's Changed
* fix: fixing incorrect import issue by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1414


**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.7.5...1.7.6

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.7.6)

---

## 1.7.5: 1.7.5
**Published:** 2025-03-16

## What's Changed
* docs: improve documentation structure with visual diagrams by @jxnl in https://github.com/instructor-ai/instructor/pull/1399
* Adding Structured Outputs for Mistral by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1391
* Docs/update contributing guide by @jxnl in https://github.com/instructor-ai/instructor/pull/1407
* Updated SQL Model Example Docs for using SkipJsonSchema by @fjooord in https://github.com/instructor-ai/instructor/pull/1410
* Adding support for the GenAI Sdk by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1393
* Update UV reps by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1411

## New Contributors
* @fjooord made their first contribution in https://github.com/instructor-ai/instructor/pull/1410

**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.7.4...1.7.5

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.7.5)

---

## 1.7.4: 1.7.4
**Published:** 2025-03-12

## What's Changed
* fix: adding static assets so that we can use them in our tests by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1387
* fix: update links to point to our repo files by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1388
* feat: Adding support for Open Router by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1386
* Updating docs and bumping Anthropic version by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1396


**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.7.3...1.7.4

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.7.4)

---

## 1.7.3: 1.7.3
**Published:** 2025-03-06

## What's Changed
* feat: add new article on migrating to uv by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1284
* Fix Markdown Titles by @Vinnie-Palazeti in https://github.com/instructor-ai/instructor/pull/1298
* chore: update run.py by @eltociear in https://github.com/instructor-ai/instructor/pull/1295
* Use GEMINI_JSON as default by @dylanjcastillo in https://github.com/instructor-ai/instructor/pull/1286
* Add Deepseek Reasoning example by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1334
* fix: vertex async example by @domenicocinque in https://github.com/instructor-ai/instructor/pull/1355
* Programmatically remove control characters from LLM response by @xtzie in https://github.com/instructor-ai/instructor/pull/1367
* feat: Add support for perplexity sonar by @charlieyou in https://github.com/instructor-ai/instructor/pull/1319
* Update vertex.md by @aryzle in https://github.com/instructor-ai/instructor/pull/1321
* Support for Sonnet 3.7 Reasoning for ANTRHOPIC_JSON  by @A-F-V in https://github.com/instructor-ai/instructor/pull/1361
* Support for aws bedrock using boto3 by @imZain448 in https://github.com/instructor-ai/instructor/pull/1287
* Standardize docs with claude code by @jxnl in https://github.com/instructor-ai/instructor/pull/1369
* feat: optimizations  by @jxnl in https://github.com/instructor-ai/instructor/pull/1373

## New Contributors
* @Vinnie-Palazeti made their first contribution in https://github.com/instructor-ai/instructor/pull/1298
* @domenicocinque made their first contribution in https://github.com/instructor-ai/instructor/pull/1355
* @xtzie made their first contribution in https://github.com/instructor-ai/instructor/pull/1367
* @charlieyou made their first contribution in https://github.com/instructor-ai/instructor/pull/1319
* @aryzle made their first contribution in https://github.com/instructor-ai/instructor/pull/1321
* @A-F-V made their first contribution in https://github.com/instructor-ai/instructor/pull/1361
* @imZain448 made their first contribution in https://github.com/instructor-ai/instructor/pull/1287

**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.7.2...1.7.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.7.3)

---

## 1.7.2: 1.7.2
**Published:** 2024-12-26

## What's Changed
* Migrate to UV by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1280


**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.7.1...1.7.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.7.2)

---

## 1.7.1: 1.7.1
**Published:** 2024-12-25

## What's Changed
* feat: added cortex documentation by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1225
* chore(deps): bump the poetry group across 1 directory with 24 updates by @dependabot in https://github.com/instructor-ai/instructor/pull/1236
* docs: Add missing section headers and fix broken links by @devin-ai-integration in https://github.com/instructor-ai/instructor/pull/1232
* feat: added a new dag article by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1246
* feat: added new article on generating llm metadata by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1249
* fixes #1252 by @hnalla in https://github.com/instructor-ai/instructor/pull/1254
* Update google.md by @Filimoa in https://github.com/instructor-ai/instructor/pull/1251
* fix: BatchJob is updated to work with current OpenAi batch request format by @aomi in https://github.com/instructor-ai/instructor/pull/1240
* Update simple_type.py by @stevenbedrick in https://github.com/instructor-ai/instructor/pull/1247
* Fixing Pyright Errors by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1267
* feat: add Parallel Tool mode for Vertex AI by @devjn in https://github.com/instructor-ai/instructor/pull/1217
* fix: Updated broken contributors profile link in README.md by @gokborayilmaz in https://github.com/instructor-ai/instructor/pull/1275
* Adding support for Gemini-8b and 2.0 by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1274
* fix: update poetry.lock by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1278

## New Contributors
* @hnalla made their first contribution in https://github.com/instructor-ai/instructor/pull/1254
* @Filimoa made their first contribution in https://github.com/instructor-ai/instructor/pull/1251
* @aomi made their first contribution in https://github.com/instructor-ai/instructor/pull/1240
* @stevenbedrick made their first contribution in https://github.com/instructor-ai/instructor/pull/1247
* @devjn made their first contribution in https://github.com/instructor-ai/instructor/pull/1217
* @gokborayilmaz made their first contribution in https://github.com/instructor-ai/instructor/pull/1275

**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.7.0...1.7.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.7.1)

---

## 1.7.0: 1.7.0
**Published:** 2024-11-27

## What's Changed
* feat: adding new article on gemini citations by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1186
* docs: restructure navigation and fix code formatting by @devin-ai-integration in https://github.com/instructor-ai/instructor/pull/1191
* fix: remove table by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1196
* Remove instructor-hub by @devin-ai-integration in https://github.com/instructor-ai/instructor/pull/1197
* feat: Writer integration by @yanomaly in https://github.com/instructor-ai/instructor/pull/1167
* Adding new tidy table article by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1204
* Update cumulative_reason.md by @OxfordOutlander in https://github.com/instructor-ai/instructor/pull/1205
* docs: add learnprompting to prompting docs description by @attanavaid in https://github.com/instructor-ai/instructor/pull/1176
* Fix tools for OpenAI messages by @chris-sanders in https://github.com/instructor-ai/instructor/pull/1194
* Edits to batch.py to support Anthropic batch API by @economy in https://github.com/instructor-ai/instructor/pull/1193
* Support nested generics with partial by @mwildehahn in https://github.com/instructor-ai/instructor/pull/1207
* docs: update installation and usage examples for LLM integrations by @jxnl in https://github.com/instructor-ai/instructor/pull/1210
* feat: enhance multimodal support for images and audio in instructor by @jxnl in https://github.com/instructor-ai/instructor/pull/1212
* fix: adding type ignore for pyright by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1215
* feat: added deepseek page by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1214

## New Contributors
* @devin-ai-integration made their first contribution in https://github.com/instructor-ai/instructor/pull/1191
* @yanomaly made their first contribution in https://github.com/instructor-ai/instructor/pull/1167
* @attanavaid made their first contribution in https://github.com/instructor-ai/instructor/pull/1176
* @chris-sanders made their first contribution in https://github.com/instructor-ai/instructor/pull/1194
* @economy made their first contribution in https://github.com/instructor-ai/instructor/pull/1193

**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.6.4...1.7.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.7.0)

---

## 1.6.4: 1.6.4
**Published:** 2024-11-14

## What's Changed
* docs: fix typo in multimodal by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1101
* fix: added requests as a dependency by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1102
* feat: add blog post and example for LLM-based reranker by @jxnl in https://github.com/instructor-ai/instructor/pull/1115
* ci: add AI labeler workflow for issues and pull requests by @jxnl in https://github.com/instructor-ai/instructor/pull/1126
* fix: typo changes by @nawed2611 in https://github.com/instructor-ai/instructor/pull/1125
* gpt 3.5 turbo updated to gpt-40-mini since July 2024 it is recommende… by @sahibpreetsingh12 in https://github.com/instructor-ai/instructor/pull/1122
* chore(deps): bump the poetry group across 1 directory with 18 updates by @dependabot in https://github.com/instructor-ai/instructor/pull/1117
* doc(blog): added Burr link; fixed date and formatting by @zilto in https://github.com/instructor-ai/instructor/pull/1099
* Fixing lint errors in concepts including hooks by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1088
* Fix spelling and grammar error by @terrchen in https://github.com/instructor-ai/instructor/pull/1121
* Patching Anthropic System by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1130
* fix: updated scope of pytest fixture to be function based by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1131
* Fix AI Labeler YAML formatting by @jlowin in https://github.com/instructor-ai/instructor/pull/1127
* fix: OpenAI prompt details and completion tokens details missing from total usage by @ivanbelenky in https://github.com/instructor-ai/instructor/pull/1105
* fix: `max_retries` typing by @jordyjwilliams in https://github.com/instructor-ai/instructor/pull/1135
* feat: Adding new blog post by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1162
* fix: use SandboxedEnvironment in templating by @dylanjcastillo in https://github.com/instructor-ai/instructor/pull/1168
* feat: Add Gemini PDF example by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1163
* fix: fixed up tenacity link by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1173
* feat: added new mixin to modify partial parsing behaviour by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1152
* fix: removed use_async flag in cerebras client by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1179
* fix: bump jiter dep by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1180
* fix: bump 1.6.3 to 1.6.4 by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1181

## New Contributors
* @nawed2611 made their first contribution in https://github.com/instructor-ai/instructor/pull/1125
* @sahibpreetsingh12 made their first contribution in https://github.com/instructor-ai/instructor/pull/1122
* @dependabot made their first contribution in https://github.com/instructor-ai/instructor/pull/1117
* @terrchen made their first contribution in https://github.com/instructor-ai/instructor/pull/1121
* @jlowin made their first contribution in https://github.com/instructor-ai/instructor/pull/1127
* @ivanbelenky made their first contribution in https://github.com/instructor-ai/instructor/pull/1105
* @jordyjwilliams made their first contribution in https://github.com/instructor-ai/instructor/pull/1135
* @dylanjcastillo made their first contribution in https://github.com/instructor-ai/instructor/pull/1168

**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.6.3...1.6.4

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.6.4)

---

## 1.6.3: 1.6.3
**Published:** 2024-10-21

## What's Changed
* docs: update example to use file_path arg; reflecting updated BatchJob.create_from_messages by @goutham794 in https://github.com/instructor-ai/instructor/pull/1096
* blog: Youtube flashcards with Instructor + Burr by @zilto in https://github.com/instructor-ai/instructor/pull/1094
* docs: update complexity_based.md by @eltociear in https://github.com/instructor-ai/instructor/pull/1098
* feat: anthropic batching code by @jxnl in https://github.com/instructor-ai/instructor/pull/1064
* Feat: Enhance multimodality by @arcaputo3 in https://github.com/instructor-ai/instructor/pull/1070
* feat: add audio support with new `Audio` class and update documentation by @jxnl in https://github.com/instructor-ai/instructor/pull/1095

## New Contributors
* @goutham794 made their first contribution in https://github.com/instructor-ai/instructor/pull/1096
* @zilto made their first contribution in https://github.com/instructor-ai/instructor/pull/1094

**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.6.2...1.6.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.6.3)

---

## 1.6.2: 1.6.2
**Published:** 2024-10-17

## What's Changed
* fix: Added off and clear proeprty to Instructor base class  by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1087
* Bumping version to 1.6.2 by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1090


**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.6.1...1.6.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.6.2)

---

## 1.6.1: 1.6.1
**Published:** 2024-10-17

## What's Changed
* Added Jinja2 as a dependency by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1084


**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.6.0...1.6.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.6.1)

---

## 1.6.0: 1.6.0
**Published:** 2024-10-17

## What's Changed
* Fix compatibility with custom dicts for multimodal message content by @mjvdvlugt in https://github.com/instructor-ai/instructor/pull/1053
* Upgrade tenacity dependencity to include 9.0.0 by @Cokral in https://github.com/instructor-ai/instructor/pull/1042
* Updating examples by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1049
* Adding support for getattrs so that we can access normal methods on wrapped clients by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1061
* fix: clean up cohere templating by @jxnl in https://github.com/instructor-ai/instructor/pull/1030
* feat: implement hooks by @jxnl in https://github.com/instructor-ai/instructor/pull/1065
* Disabling Prompting Tips by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1069
* fix: Refactor reasking logic  by @jxnl in https://github.com/instructor-ai/instructor/pull/1071
* fix: update gemini's `safety_settings` by @alxpez in https://github.com/instructor-ai/instructor/pull/1057
* Fix examples by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1077
* Docs: Clean up failing example tests by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1079
* Add Fireworks Client  by @ivanleomk in https://github.com/instructor-ai/instructor/pull/1073

## New Contributors
* @mjvdvlugt made their first contribution in https://github.com/instructor-ai/instructor/pull/1053
* @Cokral made their first contribution in https://github.com/instructor-ai/instructor/pull/1042
* @alxpez made their first contribution in https://github.com/instructor-ai/instructor/pull/1057

**Full Changelog**: https://github.com/instructor-ai/instructor/compare/1.5.2...1.6.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.6.0)

---

## 1.5.2: 1.5.2
**Published:** 2024-10-08

## What's Changed
* Add github dependabot to keep dependencies updated by @noxan in https://github.com/jxnl/instructor/pull/895
* Fixed up Cerebras Article edits by @ivanleomk in https://github.com/jxnl/instructor/pull/1043
* feat: support multimodal by @jxnl in https://github.com/jxnl/instructor/pull/1045
* fix: Add parse_from_string method to BatchJob by @kwilsonmg in https://github.com/jxnl/instructor/pull/1033
* Fix Build Errors and update copy by @ivanleomk in https://github.com/jxnl/instructor/pull/1044
* Bump version and add partial support by @ivanleomk in https://github.com/jxnl/instructor/pull/1047


**Full Changelog**: https://github.com/jxnl/instructor/compare/1.5.1...1.5.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.5.2)

---

## 1.5.1: 1.5.1
**Published:** 2024-10-04

## What's Changed
* Update fake-data.md by @CodyBontecou in https://github.com/jxnl/instructor/pull/1034
* fix: refactor handle_response_model by @jxnl in https://github.com/jxnl/instructor/pull/1032
* Added temperature parameter to RequestBody by @kwilsonmg in https://github.com/jxnl/instructor/pull/1019
* docs: move mention of `max_retries` to the correct section by @hartshorne in https://github.com/jxnl/instructor/pull/1017
* doc : Add missing import in documentation example by @geekloper in https://github.com/jxnl/instructor/pull/1016

## New Contributors
* @CodyBontecou made their first contribution in https://github.com/jxnl/instructor/pull/1034
* @hartshorne made their first contribution in https://github.com/jxnl/instructor/pull/1017
* @geekloper made their first contribution in https://github.com/jxnl/instructor/pull/1016

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.5.0...1.5.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.5.1)

---

## 1.5.0: 1.5.0
**Published:** 2024-09-30

## What's Changed
* doc: add newsletter link by @jxnl in https://github.com/jxnl/instructor/pull/1012
* Updated Caching concepts to update prompt by @ivanleomk in https://github.com/jxnl/instructor/pull/998
* Expand litellm anthropic compatibility by @JohanBekker in https://github.com/jxnl/instructor/pull/958
* feat: implement jinja templating and rename kwarg to `context` by @jxnl in https://github.com/jxnl/instructor/pull/1011
* Fixed new templating feature throwing an error for gemini by @ivanleomk in https://github.com/jxnl/instructor/pull/1021
* Added new Response Body article by @ivanleomk in https://github.com/jxnl/instructor/pull/1024
* Fixed up poetry dependencies and google gemini bug with jinja templating by @ivanleomk in https://github.com/jxnl/instructor/pull/1023
* Bump version to 1.5 by @ivanleomk in https://github.com/jxnl/instructor/pull/1028

## New Contributors
* @JohanBekker made their first contribution in https://github.com/jxnl/instructor/pull/958

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.4.3...1.5.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.5.0)

---

## 1.4.3: 1.4.3
**Published:** 2024-09-19

## What's Changed
* Fixed up a new article for prompt caching by @ivanleomk in https://github.com/jxnl/instructor/pull/997
* fix(rag-and-beyond.md): Formatting by @PLNech in https://github.com/jxnl/instructor/pull/1006
* chore(exact_citations.md): Fix punctuation (extra . after a !) by @PLNech in https://github.com/jxnl/instructor/pull/1004
* Fixed up failing test cases for partial parsing by @ivanleomk in https://github.com/jxnl/instructor/pull/1001
* Bump Anthropic Version by @ivanleomk in https://github.com/jxnl/instructor/pull/1002
* test: add partial parsing check by @mrdkucher in https://github.com/jxnl/instructor/pull/1007
* Tentative Fix for Mistral Fix by @ivanleomk in https://github.com/jxnl/instructor/pull/985
* Fixed up support for list content types when used with Gemini by @ivanleomk in https://github.com/jxnl/instructor/pull/999

## New Contributors
* @PLNech made their first contribution in https://github.com/jxnl/instructor/pull/1006

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.4.2...1.4.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.4.3)

---

## 1.4.2: 1.4.2
**Published:** 2024-09-14

## What's Changed
* Fixed typo in the installation command by @ivanleomk in https://github.com/jxnl/instructor/pull/983
* Adding support for O1 by @ivanleomk in https://github.com/jxnl/instructor/pull/991
* fix: handle whitespace in json streams by @mrdkucher in https://github.com/jxnl/instructor/pull/995
* Bumping the version of instructor to 1.4.2 by @ivanleomk in https://github.com/jxnl/instructor/pull/992
* Fixing blog typo for post "Should I Be Using Structured Outputs?" by @kwilsonmg in https://github.com/jxnl/instructor/pull/993

## New Contributors
* @mrdkucher made their first contribution in https://github.com/jxnl/instructor/pull/995
* @kwilsonmg made their first contribution in https://github.com/jxnl/instructor/pull/993

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.4.1...1.4.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.4.2)

---

## 1.4.1: 1.4.1
**Published:** 2024-09-06

## What's Changed
* Correct small typos on Structured Output post by @ivanleomk in https://github.com/jxnl/instructor/pull/945
* Modified Conclusion of Structured Outputs Post by @ivanleomk in https://github.com/jxnl/instructor/pull/950
* Bugfix: Literal while streaming does not work by @roeybc in https://github.com/jxnl/instructor/pull/948
* Helping fix some Gemini errors by @ivanleomk in https://github.com/jxnl/instructor/pull/955
* skip test if version less than 3.10 by @sreeprasannar in https://github.com/jxnl/instructor/pull/944
* Adding support for multi-modal file input for Vertex AI by @smwitkowski in https://github.com/jxnl/instructor/pull/947
* Fix Issues  by @ivanleomk in https://github.com/jxnl/instructor/pull/966
* feat: gemini tool calling support by @ssonal in https://github.com/jxnl/instructor/pull/726
* fix: ensure that utf-8 characters are not translated into \uXXXX format by @ivanleomk in https://github.com/jxnl/instructor/pull/965
* See if refusal attribute exists in ChatCompletionMessage before referencing it by @callmephilip in https://github.com/jxnl/instructor/pull/962
* Fixed up a warning for the relevant clients by @ivanleomk in https://github.com/jxnl/instructor/pull/974
* Fix: Bump version for Jiter by @paulelliotco in https://github.com/jxnl/instructor/pull/964
* Change Gemini to use Tools by default by @ivanleomk in https://github.com/jxnl/instructor/pull/981

## New Contributors
* @roeybc made their first contribution in https://github.com/jxnl/instructor/pull/948
* @sreeprasannar made their first contribution in https://github.com/jxnl/instructor/pull/944
* @smwitkowski made their first contribution in https://github.com/jxnl/instructor/pull/947
* @callmephilip made their first contribution in https://github.com/jxnl/instructor/pull/962
* @paulelliotco made their first contribution in https://github.com/jxnl/instructor/pull/964

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.4.0...1.4.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.4.1)

---

## 1.4.0: 1.4.0
**Published:** 2024-08-22

## What's Changed
* Fix debug log exception in retry_async by @mattheath in https://github.com/jxnl/instructor/pull/884
* Formatted Docs by @ivanleomk in https://github.com/jxnl/instructor/pull/864
* Anthropic IncompleteOutputException was never triggered for tools and JSON modes by @palako in https://github.com/jxnl/instructor/pull/848
* Fix for Flaky Test Issue #853 by @DonovanAD in https://github.com/jxnl/instructor/pull/891
* revise prompt design docs [zero-shot] by @shreya-51 in https://github.com/jxnl/instructor/pull/865
* Corrected some typos. by @atbradley in https://github.com/jxnl/instructor/pull/905
* Pyright Errors by @ivanleomk in https://github.com/jxnl/instructor/pull/900
* Update 4-validation.ipynb by @ashkanrdn in https://github.com/jxnl/instructor/pull/932
* Fix typo in handle_response_model (anthropic system message): responsd -> respond by @timlod in https://github.com/jxnl/instructor/pull/904
* Remove Async Validation in process async by @ivanleomk in https://github.com/jxnl/instructor/pull/933
* Adding support for structured outputs by @ivanleomk in https://github.com/jxnl/instructor/pull/938
* Update vertexai.md fix typo by @lawrencecchen in https://github.com/jxnl/instructor/pull/943
* Resolve duplicate test function name by @noxan in https://github.com/jxnl/instructor/pull/894

## New Contributors
* @mattheath made their first contribution in https://github.com/jxnl/instructor/pull/884
* @palako made their first contribution in https://github.com/jxnl/instructor/pull/848
* @DonovanAD made their first contribution in https://github.com/jxnl/instructor/pull/891
* @atbradley made their first contribution in https://github.com/jxnl/instructor/pull/905
* @ashkanrdn made their first contribution in https://github.com/jxnl/instructor/pull/932
* @timlod made their first contribution in https://github.com/jxnl/instructor/pull/904
* @lawrencecchen made their first contribution in https://github.com/jxnl/instructor/pull/943

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.3.7...1.4.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.4.0)

---

## 1.3.7: 1.3.7
**Published:** 2024-07-24

## What's Changed
* Moved Cohere import by @ivanleomk in https://github.com/jxnl/instructor/pull/874


**Full Changelog**: https://github.com/jxnl/instructor/compare/1.3.6...1.3.7

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.3.7)

---

## 1.3.5: 1.3.5
**Published:** 2024-07-17

## What's Changed
* prompting docs by @shreya-51 in https://github.com/jxnl/instructor/pull/786
* Fixed up an example for RAR and RE2 by @ivanleomk in https://github.com/jxnl/instructor/pull/790
* Added an index page by @ivanleomk in https://github.com/jxnl/instructor/pull/791
* fix: async from_litellm by @adrienbrault in https://github.com/jxnl/instructor/pull/783
* Update maybe.md by @r41ng3l in https://github.com/jxnl/instructor/pull/781
* Update usage.md 'constructor usage list' command documentation by @r41ng3l in https://github.com/jxnl/instructor/pull/770
* Add prompting docs tests by @jxnl in https://github.com/jxnl/instructor/pull/794
* docs: typo fix by @rishabgit in https://github.com/jxnl/instructor/pull/795
* Add explicit check for jsonref dep in vertexai client import guard by @lemontheme in https://github.com/jxnl/instructor/pull/797
* Fixed up Self-Ask Example by @ivanleomk in https://github.com/jxnl/instructor/pull/792
* Added some new prompt techniques by @ivanleomk in https://github.com/jxnl/instructor/pull/809
* prompt docs by @shreya-51 in https://github.com/jxnl/instructor/pull/793
* Validate anthropic_tool function args as json by @woodbridge in https://github.com/jxnl/instructor/pull/779
* Fix: Resolve create_model() TypeError in Partial class by @slavakurilyak in https://github.com/jxnl/instructor/pull/801
* add client parameter to instructor.Intructions by @bhomass in https://github.com/jxnl/instructor/pull/814
* Added new techniques by @ivanleomk in https://github.com/jxnl/instructor/pull/810
* prompt docs by @shreya-51 in https://github.com/jxnl/instructor/pull/813
* render gpt4o url by @rshah713 in https://github.com/jxnl/instructor/pull/826
* skeleton of thought prompting doc by @shreya-51 in https://github.com/jxnl/instructor/pull/824
* Bugfix: enable anthropic streaming support with partials by @ssonal in https://github.com/jxnl/instructor/pull/825
* docs(examples, navigation): add local classification tutorial and update navigation by @jxnl in https://github.com/jxnl/instructor/pull/830
* sg_icl prompting doc by @shreya-51 in https://github.com/jxnl/instructor/pull/829
* Synthetic Data Notebook by @ivanleomk in https://github.com/jxnl/instructor/pull/839
* feat: add blog post and example script for extracting YouTube video chapters using OpenAI models by @jxnl in https://github.com/jxnl/instructor/pull/831
* Added COSP by @ivanleomk in https://github.com/jxnl/instructor/pull/823
* Fixed up Max Mutual information example by @ivanleomk in https://github.com/jxnl/instructor/pull/842
* Added support for Anthropic system parameter by @ivanleomk in https://github.com/jxnl/instructor/pull/833
* knn prompting doc by @shreya-51 in https://github.com/jxnl/instructor/pull/845
* Fixed up additional functionality for the batch job article by @ivanleomk in https://github.com/jxnl/instructor/pull/843
* Fixed up new pydantic version by @ivanleomk in https://github.com/jxnl/instructor/pull/847
* Bump Tenacity Version by @ivanleomk in https://github.com/jxnl/instructor/pull/851

## New Contributors
* @adrienbrault made their first contribution in https://github.com/jxnl/instructor/pull/783
* @r41ng3l made their first contribution in https://github.com/jxnl/instructor/pull/781
* @woodbridge made their first contribution in https://github.com/jxnl/instructor/pull/779
* @slavakurilyak made their first contribution in https://github.com/jxnl/instructor/pull/801
* @bhomass made their first contribution in https://github.com/jxnl/instructor/pull/814
* @rshah713 made their first contribution in https://github.com/jxnl/instructor/pull/826

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.3.4...1.3.5

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.3.5)

---

## 1.3.4: 1.3.4
**Published:** 2024-06-25

## What's Changed
* typo fix and rephrasing suggestion by @lukaskf in https://github.com/jxnl/instructor/pull/756
* Fix the link to use the cloudflare docs by @ivanleomk in https://github.com/jxnl/instructor/pull/753
* Updated the Documentation by @ivanleomk in https://github.com/jxnl/instructor/pull/751
* Fixed Cohere retries by @ionflow in https://github.com/jxnl/instructor/pull/761
* Added Vertex AI JSON Mode by @ajac-zero in https://github.com/jxnl/instructor/pull/750
* Fix heading indentation in the getting started section of the docs by @RensDimmendaal in https://github.com/jxnl/instructor/pull/744
* Anthropic client. Prevent empty generator when streaming by @lemontheme in https://github.com/jxnl/instructor/pull/728
* Add Gemini via OpenAI Client Support Documentation by @bllchmbrs in https://github.com/jxnl/instructor/pull/736
* rename batch to bulk/async, to avoid confusion with OpenAI's batch APIs by @avyfain in https://github.com/jxnl/instructor/pull/765
* Disabling Pydantic Error by @ivanleomk in https://github.com/jxnl/instructor/pull/757
* feat: add support for typeddicts by @ivanleomk in https://github.com/jxnl/instructor/pull/758
* feat: prompt engineering cookbooks by @shreya-51 in https://github.com/jxnl/instructor/pull/764
* feat: new cli for batch jobs by @ivanleomk in https://github.com/jxnl/instructor/pull/754
* zero-shot prompting docs by @shreya-51 in https://github.com/jxnl/instructor/pull/780

## New Contributors
* @lukaskf made their first contribution in https://github.com/jxnl/instructor/pull/756
* @RensDimmendaal made their first contribution in https://github.com/jxnl/instructor/pull/744
* @avyfain made their first contribution in https://github.com/jxnl/instructor/pull/765

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.3.3...1.3.4

## What's Changed
* typo fix and rephrasing suggestion by @lukaskf in https://github.com/jxnl/instructor/pull/756
* Fix the link to use the cloudflare docs by @ivanleomk in https://github.com/jxnl/instructor/pull/753
* Updated the Documentation by @ivanleomk in https://github.com/jxnl/instructor/pull/751
* Fixed Cohere retries by @ionflow in https://github.com/jxnl/instructor/pull/761
* Added Vertex AI JSON Mode by @ajac-zero in https://github.com/jxnl/instructor/pull/750
* Fix heading indentation in the getting started section of the docs by @RensDimmendaal in https://github.com/jxnl/instructor/pull/744
* Anthropic client. Prevent empty generator when streaming by @lemontheme in https://github.com/jxnl/instructor/pull/728
* Add Gemini via OpenAI Client Support Documentation by @bllchmbrs in https://github.com/jxnl/instructor/pull/736
* rename batch to bulk/async, to avoid confusion with OpenAI's batch APIs by @avyfain in https://github.com/jxnl/instructor/pull/765
* Disabling Pydantic Error by @ivanleomk in https://github.com/jxnl/instructor/pull/757
* feat: add support for typeddicts by @ivanleomk in https://github.com/jxnl/instructor/pull/758
* feat: prompt engineering cookbooks by @shreya-51 in https://github.com/jxnl/instructor/pull/764
* feat: new cli for batch jobs by @ivanleomk in https://github.com/jxnl/instructor/pull/754
* zero-shot prompting docs by @shreya-51 in https://github.com/jxnl/instructor/pull/780
* Updated Pyproject.toml to publish a new version of Instructor by @ivanleomk in https://github.com/jxnl/instructor/pull/785

## New Contributors
* @lukaskf made their first contribution in https://github.com/jxnl/instructor/pull/756
* @RensDimmendaal made their first contribution in https://github.com/jxnl/instructor/pull/744
* @avyfain made their first contribution in https://github.com/jxnl/instructor/pull/765

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.3.3...1.3.4

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.3.4)

---

## 1.3.3: 1.3.3
**Published:** 2024-06-11

## What's Changed
* refactor(simple_type, ModelAdapter): update type checking and refactor model creation by @jxnl in https://github.com/jxnl/instructor/pull/710
* Fix response UnboundError when request fails and custom `tenacity.Retrying` is used by @lazyhope in https://github.com/jxnl/instructor/pull/713
* [fixes #721] Switch away from Anthropic beta interface for tools. by @lemontheme in https://github.com/jxnl/instructor/pull/723
* Add Support for VertexAI Gemini by @ajac-zero in https://github.com/jxnl/instructor/pull/711
* async gemini support by @Cruppelt in https://github.com/jxnl/instructor/pull/719
* fix: parallel unions by @vinchg in https://github.com/jxnl/instructor/pull/734
* typo fix document_segmentation.md by @NicolaiLolansen in https://github.com/jxnl/instructor/pull/730
* Sync `pyproject.toml` and `poetry.lock` files by @jlondonobo in https://github.com/jxnl/instructor/pull/729
* Added Jiter Support by @ivanleomk in https://github.com/jxnl/instructor/pull/745
* Iterable Workaround by @ivanleomk in https://github.com/jxnl/instructor/pull/737

## New Contributors
* @lemontheme made their first contribution in https://github.com/jxnl/instructor/pull/723
* @ajac-zero made their first contribution in https://github.com/jxnl/instructor/pull/711
* @vinchg made their first contribution in https://github.com/jxnl/instructor/pull/734
* @NicolaiLolansen made their first contribution in https://github.com/jxnl/instructor/pull/730

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.3.2...1.3.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.3.3)

---

## 1.3.2: 1.3.2
**Published:** 2024-05-27

## What's Changed
* Adding gpt4o vision example  by @karbon0x in https://github.com/jxnl/instructor/pull/702
* Fixed incorrect/missing arguments by @Elektra58 in https://github.com/jxnl/instructor/pull/708
* Fixed incorrect argument by @Elektra58 in https://github.com/jxnl/instructor/pull/707
* Fixed a typo by @yasoob in https://github.com/jxnl/instructor/pull/705
* restore async groq functionality by @cmishra in https://github.com/jxnl/instructor/pull/704
* Improve gemini model robustness by @ssonal in https://github.com/jxnl/instructor/pull/701

## New Contributors
* @karbon0x made their first contribution in https://github.com/jxnl/instructor/pull/702
* @Elektra58 made their first contribution in https://github.com/jxnl/instructor/pull/708
* @yasoob made their first contribution in https://github.com/jxnl/instructor/pull/705
* @cmishra made their first contribution in https://github.com/jxnl/instructor/pull/704

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.3.1...1.3.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.3.2)

---

## 1.3.1: 1.3.1
**Published:** 2024-05-23

## What's Changed
* Fix typos in README.md by @AmgadHasan in https://github.com/jxnl/instructor/pull/699
* Fix failure checking for "google.generativeai' import spec by @dbmikus in https://github.com/jxnl/instructor/pull/698

## New Contributors
* @AmgadHasan made their first contribution in https://github.com/jxnl/instructor/pull/699
* @dbmikus made their first contribution in https://github.com/jxnl/instructor/pull/698

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.3.0...1.3.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.3.1)

---

## 1.3.0: 1.3.0
**Published:** 2024-05-23

## What's Changed
* Update groq.md by @frankbaele in https://github.com/jxnl/instructor/pull/651
* Added gpt-4o to model costs and model names by @st4r0 in https://github.com/jxnl/instructor/pull/671
* Update Groq documentation and examples to use preferred patching method by @NasonZ in https://github.com/jxnl/instructor/pull/663
* anthropic force tool by @Cruppelt in https://github.com/jxnl/instructor/pull/681
* maybe results typo fix by @rbraddev in https://github.com/jxnl/instructor/pull/686
* Parea Blogpost by @joschkabraun in https://github.com/jxnl/instructor/pull/673
* Fix typo in philosophy.md by @deeplook in https://github.com/jxnl/instructor/pull/677
* Update mode.py to warn in `Mode.FUNCTIONS` access vs. in `__new__` by @boydgreenfield in https://github.com/jxnl/instructor/pull/678
* Fix handling of snapshot_ids ("gpt-4-turbo-2024-04-09" and "gpt-4o-2024-05-13") and alias "gpt-4-turbo". by @st4r0 in https://github.com/jxnl/instructor/pull/672
* Update ollama.md by @MeDott29 in https://github.com/jxnl/instructor/pull/635
* Fixed up discord link by @ivanleomk in https://github.com/jxnl/instructor/pull/690
* Enrich IncompleteOutputException with completion context by @lukszamarcin in https://github.com/jxnl/instructor/pull/683
* Anthropic streaming support by @ssonal in https://github.com/jxnl/instructor/pull/682
* results rename by @rbraddev in https://github.com/jxnl/instructor/pull/692
* Updates to Parea blog by @joschkabraun in https://github.com/jxnl/instructor/pull/695
* Fix typo in blog by @joschkabraun in https://github.com/jxnl/instructor/pull/696
* Update `Mode.MD_JSON` and add `Provider.DATABRICKS` by @arcaputo3 in https://github.com/jxnl/instructor/pull/691
* Add basic support for gemini models by @ssonal in https://github.com/jxnl/instructor/pull/684

## New Contributors
* @frankbaele made their first contribution in https://github.com/jxnl/instructor/pull/651
* @st4r0 made their first contribution in https://github.com/jxnl/instructor/pull/671
* @NasonZ made their first contribution in https://github.com/jxnl/instructor/pull/663
* @rbraddev made their first contribution in https://github.com/jxnl/instructor/pull/686
* @deeplook made their first contribution in https://github.com/jxnl/instructor/pull/677
* @lukszamarcin made their first contribution in https://github.com/jxnl/instructor/pull/683
* @ssonal made their first contribution in https://github.com/jxnl/instructor/pull/682
* @arcaputo3 made their first contribution in https://github.com/jxnl/instructor/pull/691

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.2.6...1.3.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.3.0)

---

## 1.2.6: 1.2.6
**Published:** 2024-05-09

## What's Changed
* Import typing related imports only when type checking by @noxan in https://github.com/jxnl/instructor/pull/645
* New Logfire Article ( Fixes #640 )  by @ivanleomk in https://github.com/jxnl/instructor/pull/647
* Updated the Logfire and Fastapi article by @ivanleomk in https://github.com/jxnl/instructor/pull/648
* [docs] index watsonx example by @h0rv in https://github.com/jxnl/instructor/pull/642
* doc: Update self_critique.md by @sgrimee in https://github.com/jxnl/instructor/pull/652
* fix: Update llama-cpp-python examples to use `patch` instead of `from_openai` by @abetlen in https://github.com/jxnl/instructor/pull/656

## New Contributors
* @noxan made their first contribution in https://github.com/jxnl/instructor/pull/645
* @sgrimee made their first contribution in https://github.com/jxnl/instructor/pull/652
* @abetlen made their first contribution in https://github.com/jxnl/instructor/pull/656

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.2.5...1.2.6

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.2.6)

---

## 1.2.5: 1.2.5
**Published:** 2024-05-01

## What's Changed
* feat: add watsonx support by @h0rv in https://github.com/jxnl/instructor/pull/620
* Implement Pyright for Type-Checking by @max-muoto in https://github.com/jxnl/instructor/pull/630
* Enable PyUpgrade Ruff Rule-Set by @max-muoto in https://github.com/jxnl/instructor/pull/633
* Avoid deprecated class property stacking by @max-muoto in https://github.com/jxnl/instructor/pull/637
* Instructor with Logfire by @ivanleomk in https://github.com/jxnl/instructor/pull/639
* ANTHROPIC_JSON: allow control characters in JSON strings if strict=False by @voberoi in https://github.com/jxnl/instructor/pull/644
* Allow newer Pydantic patch versions by @bencrouse in https://github.com/jxnl/instructor/pull/643

## New Contributors
* @h0rv made their first contribution in https://github.com/jxnl/instructor/pull/620
* @max-muoto made their first contribution in https://github.com/jxnl/instructor/pull/630
* @voberoi made their first contribution in https://github.com/jxnl/instructor/pull/644
* @bencrouse made their first contribution in https://github.com/jxnl/instructor/pull/643

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.2.4...1.2.5

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.2.5)

---

## 1.2.4: 1.2.4
**Published:** 2024-04-29

## What's Changed
* feat: update and allow strict mode by @jxnl in https://github.com/jxnl/instructor/pull/618
* fix: allow openai-like clients into from_openai


**Full Changelog**: https://github.com/jxnl/instructor/compare/1.2.3...1.2.4

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.2.4)

---

## 1.2.3: 1.2.3
**Published:** 2024-04-27

## What's Changed
* Fix bullet list in README.md by @xingweitian in https://github.com/jxnl/instructor/pull/621
* Update README.md by @eltociear in https://github.com/jxnl/instructor/pull/625
* fix typo about Enum 'and' → 'an' by @inn-0 in https://github.com/jxnl/instructor/pull/626
* Fix anthropic usage and tools by @lazyhope in https://github.com/jxnl/instructor/pull/622

## New Contributors
* @xingweitian made their first contribution in https://github.com/jxnl/instructor/pull/621
* @eltociear made their first contribution in https://github.com/jxnl/instructor/pull/625

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.2.2...1.2.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.2.3)

---

## 1.2.2: 1.2.2
**Published:** 2024-04-20

## What's Changed
* From mistral by @wassim-trabelsi in https://github.com/jxnl/instructor/pull/599
* feat: custom exceptions by @jxnl in https://github.com/jxnl/instructor/pull/614

## New Contributors
* @wassim-trabelsi made their first contribution in https://github.com/jxnl/instructor/pull/599

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.2.1...1.2.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.2.2)

---

## 1.2.1: 1.2.1
**Published:** 2024-04-18

## What's Changed
* feat: basic sentiment analysis eval tests by @meta-boy in https://github.com/jxnl/instructor/pull/610
* [Ellipsis] docstring-parser 0.16 by @ellipsis-dev in https://github.com/jxnl/instructor/pull/608
* Added support for MD_JSON for Anyscale and Together by @jpetrantoni in https://github.com/jxnl/instructor/pull/611

## New Contributors
* @meta-boy made their first contribution in https://github.com/jxnl/instructor/pull/610

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.2.0...1.2.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.2.1)

---

## 1.2.0: 1.2.0
**Published:** 2024-04-14

## What's Changed
* Add support for cohere models by @lidiyam in https://github.com/jxnl/instructor/pull/585
* adding AnthropicVertex by @dlubom in https://github.com/jxnl/instructor/pull/595
* fix: typo textblocks vi-fr  in blog post by @inn-0 in https://github.com/jxnl/instructor/pull/596
* Document use of SkipJsonSchema for omitting fields by @boydgreenfield in https://github.com/jxnl/instructor/pull/597
* Support python 3.9 by @RedTachyon in https://github.com/jxnl/instructor/pull/601

## New Contributors
* @lidiyam made their first contribution in https://github.com/jxnl/instructor/pull/585
* @dlubom made their first contribution in https://github.com/jxnl/instructor/pull/595
* @boydgreenfield made their first contribution in https://github.com/jxnl/instructor/pull/597
* @RedTachyon made their first contribution in https://github.com/jxnl/instructor/pull/601

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.1.0...1.2.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.2.0)

---

## 1.1.0: 1.1.0
**Published:** 2024-04-11

## What's Changed
* docs: fixes few typos in validation-part1 by @rishabgit in https://github.com/jxnl/instructor/pull/572
* fix broken link to evals by @avangerp in https://github.com/jxnl/instructor/pull/577
* docs: fix typo in bug template by @ridoy in https://github.com/jxnl/instructor/pull/573
* deps(typer): adjust dependency range by @rushilsrivastava in https://github.com/jxnl/instructor/pull/586
* Update retry.py by @maximeobergeron in https://github.com/jxnl/instructor/pull/583
* Refactor anthropic message format to support tool messages & Allows Anthropic Bedrock clients by @lazyhope in https://github.com/jxnl/instructor/pull/579
* fix typo textblocks  vi-fr by @inn-0 in https://github.com/jxnl/instructor/pull/590

## New Contributors
* @rishabgit made their first contribution in https://github.com/jxnl/instructor/pull/572
* @avangerp made their first contribution in https://github.com/jxnl/instructor/pull/577
* @ridoy made their first contribution in https://github.com/jxnl/instructor/pull/573
* @rushilsrivastava made their first contribution in https://github.com/jxnl/instructor/pull/586
* @maximeobergeron made their first contribution in https://github.com/jxnl/instructor/pull/583
* @inn-0 made their first contribution in https://github.com/jxnl/instructor/pull/590

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.0.3...1.1.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.1.0)

---

## 1.0.3: 1.0.3
**Published:** 2024-04-05

## What's Changed
* Fixed deps for 2.7.0b01

## New Contributors
* @jd-solanki made their first contribution in https://github.com/jxnl/instructor/pull/570

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.0.2...1.0.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.0.3)

---

## 1.0.2: 1.0.2
**Published:** 2024-04-05

## What's Changed
* feat: Partial jiter by @jxnl in https://github.com/jxnl/instructor/pull/563
* feat: support anthropic tools by @jxnl in https://github.com/jxnl/instructor/pull/569
* fix: extras dependencies to truly be optional by @ameade in https://github.com/jxnl/instructor/pull/565

## New Contributors
* @ameade made their first contribution in https://github.com/jxnl/instructor/pull/565

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.0.1...1.0.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.0.2)

---

## 1.0.1: 1.0.1
**Published:** 2024-04-03

## What's Changed
* Support Groq #556 by @rabem00 in https://github.com/jxnl/instructor/pull/561
* Support Anthropic Reasking @jxnl in https://github.com/jxnl/instructor/pull/560
* Anthropic and Groq are optional installs 

## New Contributors
* @valgaze made their first contribution in https://github.com/jxnl/instructor/pull/554
* @rabem00 made their first contribution in https://github.com/jxnl/instructor/pull/561

**Full Changelog**: https://github.com/jxnl/instructor/compare/1.0.0...1.0.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.0.1)

---

## 1.0.0: 1.0.0
**Published:** 2024-04-01

## What's Changed
* refactor(OpenAISchema): improve `from_response` readability and update tests by @jxnl in https://github.com/jxnl/instructor/pull/543
* feat(instructor): introduce new client with support for different providers and sync/async operations by @jxnl in https://github.com/jxnl/instructor/pull/546


**Full Changelog**: https://github.com/jxnl/instructor/compare/0.6.8...1.0.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/1.0.0)

---

## 0.6.8: 0.6.8
**Published:** 2024-03-29

I know mypy is broken...

## What's Changed
* Add optional dependencies for anthropic and xmltodict by @jpetrantoni in https://github.com/jxnl/instructor/pull/519
* anthropic supports enum by @Cruppelt in https://github.com/jxnl/instructor/pull/524
* anthropic system prompt clean up by @Cruppelt in https://github.com/jxnl/instructor/pull/523
* Better partial support by @mwildehahn in https://github.com/jxnl/instructor/pull/527
* fix: add handling for List[non-object] types by @shreya-51 in https://github.com/jxnl/instructor/pull/521
* feat(instructor): introduce ANTHROPIC_JSON mode by @jxnl in https://github.com/jxnl/instructor/pull/542

## New Contributors
* @jpetrantoni made their first contribution in https://github.com/jxnl/instructor/pull/519
* @Cruppelt made their first contribution in https://github.com/jxnl/instructor/pull/524
* @mwildehahn made their first contribution in https://github.com/jxnl/instructor/pull/527

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.6.7...0.6.8

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.6.8)

---

## 0.6.7: 0.6.7
**Published:** 2024-03-21

fixed import error 

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.6.6...0.6.7

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.6.7)

---

## 0.6.6: 0.6.6
**Published:** 2024-03-21

## What's Changed
* fix: clean up imports for anthropic by @jxnl in https://github.com/jxnl/instructor/pull/517


**Full Changelog**: https://github.com/jxnl/instructor/compare/0.6.5...0.6.6

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.6.6)

---

## 0.6.5: 0.6.5
**Published:** 2024-03-20

## What's Changed
* Adds link to InstructorGPT by @Evanc123 in https://github.com/jxnl/instructor/pull/499
* feat: add cname by @jxnl in https://github.com/jxnl/instructor/pull/501
* Migrate docs posthog to proxy by @atbe in https://github.com/jxnl/instructor/pull/502
* fix: remove limit param from openai FileObject.list() by @aakashb09 in https://github.com/jxnl/instructor/pull/505
* Errors in Search Docs: Missing Import + Wrong Variable Name by @bllchmbrs in https://github.com/jxnl/instructor/pull/507
* Avoid double-including error message in retry when Mode.TOOLS by @ilyanekhay-uta in https://github.com/jxnl/instructor/pull/514
* feat: support anthropic (non-streaming only) by @shreya-51 in https://github.com/jxnl/instructor/pull/512

## New Contributors
* @Evanc123 made their first contribution in https://github.com/jxnl/instructor/pull/499
* @atbe made their first contribution in https://github.com/jxnl/instructor/pull/502
* @aakashb09 made their first contribution in https://github.com/jxnl/instructor/pull/505
* @ilyanekhay-uta made their first contribution in https://github.com/jxnl/instructor/pull/514
* @shreya-51 made their first contribution in https://github.com/jxnl/instructor/pull/512

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.6.4...0.6.5

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.6.5)

---

## 0.6.4: 0.6.4
**Published:** 2024-03-08

## What's Changed
* fix: big refactor of patch.py by @jxnl in https://github.com/jxnl/instructor/pull/493
* fix: updated deprecated pydantic import by @zboyles in https://github.com/jxnl/instructor/pull/494


**Full Changelog**: https://github.com/jxnl/instructor/compare/0.6.3...0.6.4

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.6.4)

---

## 0.6.3: 0.6.3
**Published:** 2024-03-06

## What's Changed
* fix: examples/citation_with_extraction/citation_fuzzy_match.py is out of sync with the website by @superkelvint in https://github.com/jxnl/instructor/pull/471
* fix: dedent json system prompt by @timothyasp in https://github.com/jxnl/instructor/pull/465
* Update youtube_clips.md by @nathan-grant in https://github.com/jxnl/instructor/pull/483
* fix: Improve type hinting, update response models handling, add logging, and fix bugs by @jxnl in https://github.com/jxnl/instructor/pull/484
* nit: fix typo: informatino -> information by @SinghCoder in https://github.com/jxnl/instructor/pull/487
* feat: Improve MD_JSON mode by @jxnl in https://github.com/jxnl/instructor/pull/490

## New Contributors
* @superkelvint made their first contribution in https://github.com/jxnl/instructor/pull/471
* @timothyasp made their first contribution in https://github.com/jxnl/instructor/pull/465
* @nathan-grant made their first contribution in https://github.com/jxnl/instructor/pull/483
* @SinghCoder made their first contribution in https://github.com/jxnl/instructor/pull/487

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.6.2...0.6.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.6.3)

---

## 0.6.2: 0.6.2
**Published:** 2024-03-01

## What's Changed
* doc: Move partial and iterable from cookbook/examples  to hub by @ethanleifer in https://github.com/jxnl/instructor/pull/452
* chore(github-actions): simplify caching and reorder setup steps by @jxnl in https://github.com/jxnl/instructor/pull/453
* chore(github-actions): optimize workflows with matrix strategy and caching by @jxnl in https://github.com/jxnl/instructor/pull/455
* doc: Fix broken doc links in README by @hammer in https://github.com/jxnl/instructor/pull/461
* doc: Update README.md by @MeDott29 in https://github.com/jxnl/instructor/pull/463
* doc:Lead extraction hub example by @Stepheni12 in https://github.com/jxnl/instructor/pull/459
* doc: Update README.md including primitive types usage by @Fakamoto in https://github.com/jxnl/instructor/pull/464
* doc: add support for mistral tool calling by @shanktt in https://github.com/jxnl/instructor/pull/467
* doc: Create py.typed by @rgbkrk in https://github.com/jxnl/instructor/pull/468
* doc: References to PHP port added to docs by @ddebowczyk in https://github.com/jxnl/instructor/pull/474
* fix: account for multiple times wrapped functions by @joschkabraun in https://github.com/jxnl/instructor/pull/476

## New Contributors
* @hammer made their first contribution in https://github.com/jxnl/instructor/pull/461
* @Stepheni12 made their first contribution in https://github.com/jxnl/instructor/pull/459
* @Fakamoto made their first contribution in https://github.com/jxnl/instructor/pull/464
* @ddebowczyk made their first contribution in https://github.com/jxnl/instructor/pull/474
* @joschkabraun made their first contribution in https://github.com/jxnl/instructor/pull/476

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.6.1...0.6.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.6.2)

---

## 0.6.1: 0.6.1
**Published:** 2024-02-20

## What's Changed
* cookbook: competitors matrix example for image extraction by @fpingham in https://github.com/jxnl/instructor/pull/346
* refactor(batch-classification,extract-table): simplify code, improve functionalities, introduce langsmith library by @jxnl in https://github.com/jxnl/instructor/pull/442
* feat(response model): introduce handling of simple types by @jxnl in https://github.com/jxnl/instructor/pull/447
* docs: update code snippets and text across multiple documentation files by @jxnl in https://github.com/jxnl/instructor/pull/450
* doc: move provider examples to hub by @ethanleifer in https://github.com/jxnl/instructor/pull/449
* docs(hub): add pandas_df.md and update mkdocs.yml by @jxnl in https://github.com/jxnl/instructor/pull/451
* blog: Langsmith blogpost  by @jxnl in https://github.com/jxnl/instructor/pull/444
* feat(docs/GPT-4 Vision Model): Add document on extracting tables from images and related functionality by @jxnl in https://github.com/jxnl/instructor/pull/443

## New Contributors
* @ethanleifer made their first contribution in https://github.com/jxnl/instructor/pull/449

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.6.0...0.6.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.6.1)

---

## 0.6.0: 0.6.0
**Published:** 2024-02-18

# Release Highlights: Version 0.6.0 🌟

We're thrilled to announce the release of Version 0.6.0 for `instructor`. This version introduces a myriad of enhancements, new features, and critical fixes that significantly improve the developer experience. Here's what's new:

### Features
- **Instructor Hub Launch:** Discover the newly introduced Instructor Hub, a central place for tutorials, examples, and a new CLI, making it easier for developers to get up and running.
- **Enhanced Patching Methods:** The introduction of new patching methods and modes brings flexibility and power to the customization capabilities of the library.
- **Blog Addition:** Dive into our latest blog post on `llama-cpp-python` and `instructor` library usage, offering insights and best practices.
- **SQLModel Integration:** A major leap forward with `feat(Instructor): integrate with SQLModel`, providing seamless integration, along with comprehensive documentation and examples.

### Improvements and Fixes
- **Workflow and Error Handling Enhancements:** Modifications to GitHub Actions and parallel processing error handling improve reliability and developer workflow.
- **Documentation Overhaul:** Significant updates to documentation, including new reference links, formatting fixes, and synchronization of requirements, ensure developers have access to the latest and most accurate information.
- **Type Annotations:** The inclusion of types to various components enhances code readability and maintainability.

### New Contributors
A special shoutout to our new contributors @ryanhalliday, @teome, @leobeeson, and @shiftbug for their valuable additions to the project.

We're excited for you to try out the new features and improvements in Version 0.6.0. Your feedback is invaluable to us, so please don't hesitate to share your thoughts and experiences as you explore this release. Happy coding!

## What's Changed
* chore: Include types to instructor.distil and tests by @savarin in https://github.com/jxnl/instructor/pull/396
* feat(Instructor): integrate with SQLModel, provide documentation and example by @shanktt in https://github.com/jxnl/instructor/pull/418
* chore: Include types to instructor.dsl by @savarin in https://github.com/jxnl/instructor/pull/419
* fix(github-actions): modify triggering conditions for workflows by @jxnl in https://github.com/jxnl/instructor/pull/420
* fix(parallel): enhance error handling in get_types_array and add test case by @jxnl in https://github.com/jxnl/instructor/pull/423
* docs(documentation): update reference link, add new file, modify mkdocs.yml by @jxnl in https://github.com/jxnl/instructor/pull/424
* docs: small formatting fixes by @ryanhalliday in https://github.com/jxnl/instructor/pull/427
* docs: Sync requirements-doc.txt with Poetry dev group till mkdocs works by @ryanhalliday in https://github.com/jxnl/instructor/pull/428
* docs(patching): introduce new patching methods and modes, update documentation by @jxnl in https://github.com/jxnl/instructor/pull/431
* fix(validation): increase max_retries from 1 to 2 by @jxnl in https://github.com/jxnl/instructor/pull/433
* feat(blog): Add new post on `llama-cpp-python` and `instructor` library usage by @jxnl in https://github.com/jxnl/instructor/pull/434
* fix: json modes - don't add json schema again in system message by @teome in https://github.com/jxnl/instructor/pull/435
* chore: Include types to instructor.patch by @savarin in https://github.com/jxnl/instructor/pull/422
* Revert "chore: Include types to instructor.patch" by @jxnl in https://github.com/jxnl/instructor/pull/437
* feat(instructor/patch.py): change default mode from FUNCTIONS to TOOLS by @jxnl in https://github.com/jxnl/instructor/pull/436
* Include new model names in _alias.py by @leobeeson in https://github.com/jxnl/instructor/pull/426
* Update ollama.md by @shiftbug in https://github.com/jxnl/instructor/pull/438
* Update pricing of models, and include 1106 and 0125 models. by @leobeeson in https://github.com/jxnl/instructor/pull/425
* feat(Instructor): introduce Instructor Hub with tutorials, examples, and new CLI by @jxnl in https://github.com/jxnl/instructor/pull/439

## New Contributors
* @ryanhalliday made their first contribution in https://github.com/jxnl/instructor/pull/427
* @teome made their first contribution in https://github.com/jxnl/instructor/pull/435
* @leobeeson made their first contribution in https://github.com/jxnl/instructor/pull/426
* @shiftbug made their first contribution in https://github.com/jxnl/instructor/pull/438

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.5.2...0.6.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.6.0)

---

## 0.5.2: 0.5.2
**Published:** 2024-02-07

## What's Changed
* chore(pull_request_template): update to include conventional commits instructions by @jxnl in https://github.com/jxnl/instructor/pull/411
* Update __init__.py to include handling models and remove unpatch in _… by @PrathamSoni in https://github.com/jxnl/instructor/pull/409
* fix: Adding tests to make sure non-stream iterables work by @jxnl in https://github.com/jxnl/instructor/pull/413

## New Contributors
* @PrathamSoni made their first contribution in https://github.com/jxnl/instructor/pull/409

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.5.1...0.5.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.5.2)

---

## 0.5.1: 0.5.1
**Published:** 2024-02-06

## What's Changed
* Include types to instructor.function_calls and tests by @savarin in https://github.com/jxnl/instructor/pull/394
* lint documentation by @jxnl in https://github.com/jxnl/instructor/pull/403
* Test all of our documentation.  by @jxnl in https://github.com/jxnl/instructor/pull/404
* CICD: Add `set -e -o pipefail` to `ruff` and `mypy`. by @gao-hongnan in https://github.com/jxnl/instructor/pull/399
* fix: Fixed links in image to add copy  by @lakshyaag in https://github.com/jxnl/instructor/pull/367


**Full Changelog**: https://github.com/jxnl/instructor/compare/0.5.0...0.5.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.5.1)

---

## 0.5.0: 0.5.0
**Published:** 2024-02-04

## What's Changed
* Be robust to null values while updating token counts by @indigoviolet in https://github.com/jxnl/instructor/pull/359
* Together ai support, blog post by @jxnl in https://github.com/jxnl/instructor/pull/366
* Fixes prompt typo by @skrawcz in https://github.com/jxnl/instructor/pull/368
* Clean up streaming code  by @jxnl in https://github.com/jxnl/instructor/pull/377
* Types!!! by @jxnl in https://github.com/jxnl/instructor/pull/372
* Implement Parallel Function Calls with `List[Union[T]]` by @jxnl in https://github.com/jxnl/instructor/pull/378
* Attempt to implement new retires by @jxnl in https://github.com/jxnl/instructor/pull/386
* Fix sp. errors and light copy editing. by @jhochenbaum in https://github.com/jxnl/instructor/pull/388
* Remove unused imports by @savarin in https://github.com/jxnl/instructor/pull/393
* Include types to most upstream modules by @savarin in https://github.com/jxnl/instructor/pull/391
* Include types to instructor.cli.jobs by @savarin in https://github.com/jxnl/instructor/pull/392
* Fix typos by @cdreetz in https://github.com/jxnl/instructor/pull/395

## New Contributors
* @indigoviolet made their first contribution in https://github.com/jxnl/instructor/pull/359
* @skrawcz made their first contribution in https://github.com/jxnl/instructor/pull/368
* @jhochenbaum made their first contribution in https://github.com/jxnl/instructor/pull/388
* @savarin made their first contribution in https://github.com/jxnl/instructor/pull/393
* @cdreetz made their first contribution in https://github.com/jxnl/instructor/pull/395

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.4.8...0.5.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.5.0)

---

## 0.4.8: 0.4.8
**Published:** 2024-01-23

## What's Changed
* Adding support for caching async functions by @ivanleomk in https://github.com/jxnl/instructor/pull/340
* fix a few spelling mistakes & typos by @petrus-jvrensburg in https://github.com/jxnl/instructor/pull/349
* Update the readme and remove some wording duplication. by @thedayisntgray in https://github.com/jxnl/instructor/pull/351
* Add ollama run.py with completion functionality by @Tedfulk in https://github.com/jxnl/instructor/pull/352
* Ollama part2 by @jxnl in https://github.com/jxnl/instructor/pull/356

## New Contributors
* @petrus-jvrensburg made their first contribution in https://github.com/jxnl/instructor/pull/349
* @thedayisntgray made their first contribution in https://github.com/jxnl/instructor/pull/351

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.4.7...0.4.8

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.4.8)

---

## 0.4.7: 0.4.7
**Published:** 2024-01-14

Improvements with field streaming and usage tokens

## What's Changed
* Updated the Knowledge Graph article by @ivanleomk in https://github.com/jxnl/instructor/pull/327
* test ollama and litellm by @jxnl in https://github.com/jxnl/instructor/pull/326
* Revert "test ollama and litellm" by @jxnl in https://github.com/jxnl/instructor/pull/328
* Update fields.md - fix typo, missing comma by @MrJarnould in https://github.com/jxnl/instructor/pull/329
* Update function call mode and add deprecation warning by @Phodaie in https://github.com/jxnl/instructor/pull/337
* Introduce `total_usage` variable to track cumulative token usage by @lazyhope in https://github.com/jxnl/instructor/pull/343
* Field level streaming by @shanktt in https://github.com/jxnl/instructor/pull/334

## New Contributors
* @MrJarnould made their first contribution in https://github.com/jxnl/instructor/pull/329
* @lazyhope made their first contribution in https://github.com/jxnl/instructor/pull/343

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.4.6...0.4.7

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.4.7)

---

## 0.4.6: 0.4.6
**Published:** 2024-01-05

## What's Changed
* Update README.md by @lakshyaag in https://github.com/jxnl/instructor/pull/291
* doc: fix typos and grammatical errors in Concepts by @lakshyaag in https://github.com/jxnl/instructor/pull/292
* docs: example on Vision API (image to ad copy) by @lakshyaag in https://github.com/jxnl/instructor/pull/293
* Improve tutorial quality  by @jxnl in https://github.com/jxnl/instructor/pull/298
* add ellipsis.yaml config file; by @hbrooks in https://github.com/jxnl/instructor/pull/300
* Added example for using unions of models, useful for agents by @zby in https://github.com/jxnl/instructor/pull/299
* More Tutorial Updates by @jxnl in https://github.com/jxnl/instructor/pull/303
* [docs] Add example link on index page by @lakshyaag in https://github.com/jxnl/instructor/pull/305
* Integrate and Enhance Linting with Ruff by @gao-hongnan in https://github.com/jxnl/instructor/pull/295
* Update ellipsis.yaml by @jxnl in https://github.com/jxnl/instructor/pull/312
* json scheme example change by @Phodaie in https://github.com/jxnl/instructor/pull/316
* Small documentation updates by @CSRessel in https://github.com/jxnl/instructor/pull/313
* __init__.py added for testing individual files in tests/openai by @zby in https://github.com/jxnl/instructor/pull/318
* Add default openai_client in LLM Validator by @asimkhan73301 in https://github.com/jxnl/instructor/pull/311
* Mc/toolmaxretry by @marcasty in https://github.com/jxnl/instructor/pull/323
* Update `Maybe` typing by @dalberto in https://github.com/jxnl/instructor/pull/325

## New Contributors
* @lakshyaag made their first contribution in https://github.com/jxnl/instructor/pull/291
* @hbrooks made their first contribution in https://github.com/jxnl/instructor/pull/300
* @zby made their first contribution in https://github.com/jxnl/instructor/pull/299
* @CSRessel made their first contribution in https://github.com/jxnl/instructor/pull/313
* @asimkhan73301 made their first contribution in https://github.com/jxnl/instructor/pull/311
* @marcasty made their first contribution in https://github.com/jxnl/instructor/pull/323
* @dalberto made their first contribution in https://github.com/jxnl/instructor/pull/325

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.4.5...0.4.6

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.4.6)

---

## 0.4.5: 0.4.5
**Published:** 2023-12-19

## What's Changed
* Update anyscale.md by @robertnishihara in https://github.com/jxnl/instructor/pull/285
* example: Table extraction w/ Pydantic by @jxnl in https://github.com/jxnl/instructor/pull/288
* Azure support in multitask.py by @arnavw in https://github.com/jxnl/instructor/pull/290

## New Contributors
* @robertnishihara made their first contribution in https://github.com/jxnl/instructor/pull/285
* @arnavw made their first contribution in https://github.com/jxnl/instructor/pull/290

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.4.3...0.4.5

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.4.5)

---

## 0.4.3: 0.4.4
**Published:** 2023-12-17

## What's Changed
* Add logging.error for Retry logic by @jxnl in https://github.com/jxnl/instructor/pull/259
* Update contributing.md by @tadash10 in https://github.com/jxnl/instructor/pull/241
* Adds ruff linting and formatting by @ggaabe in https://github.com/jxnl/instructor/pull/262
* Json mode nested models by @shanktt in https://github.com/jxnl/instructor/pull/263
* Fix async streaming by @Anmol6 in https://github.com/jxnl/instructor/pull/261
* Add multitask tests by @jxnl in https://github.com/jxnl/instructor/pull/265
* Parse availability of dates by @jxnl in https://github.com/jxnl/instructor/pull/267
* Integrate and Enhance Type Checking with Mypy by @gao-hongnan in https://github.com/jxnl/instructor/pull/264
* Add new Mode for Anyscale's json schema schema type  by @jxnl in https://github.com/jxnl/instructor/pull/273
* Revert "Add new Mode for Anyscale's json schema schema type " by @jxnl in https://github.com/jxnl/instructor/pull/274
* Support JSON_OBJECT mode from Anyscale by @jxnl in https://github.com/jxnl/instructor/pull/275
* Updates to Tutorials  by @jxnl in https://github.com/jxnl/instructor/pull/248
* added finish reason exception IncompleteOutputException by @ionflow in https://github.com/jxnl/instructor/pull/279
* doc: small change to readablity. by @Tedfulk in https://github.com/jxnl/instructor/pull/281
* feat: add debugging for retries  by @jxnl in https://github.com/jxnl/instructor/pull/283
* blog: Third party models by @Anmol6 in https://github.com/jxnl/instructor/pull/284

## New Contributors
* @tadash10 made their first contribution in https://github.com/jxnl/instructor/pull/241
* @ggaabe made their first contribution in https://github.com/jxnl/instructor/pull/262
* @shanktt made their first contribution in https://github.com/jxnl/instructor/pull/263
* @gao-hongnan made their first contribution in https://github.com/jxnl/instructor/pull/264
* @ionflow made their first contribution in https://github.com/jxnl/instructor/pull/279
* @Tedfulk made their first contribution in https://github.com/jxnl/instructor/pull/281

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.4.2...0.4.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.4.3)

---

## 0.4.2: 0.4.2
**Published:** 2023-12-06

## What's Changed
* Opensource examples - Runpod w/Text-Generation-WebUI API Endpoint by @PhiBrandon in https://github.com/jxnl/instructor/pull/247
* Fixed the system prompt for JSON mode, enabling the use of Pydantic nested models by @aastroza in https://github.com/jxnl/instructor/pull/249
* Fix "seperate" typo by @toolittlecakes in https://github.com/jxnl/instructor/pull/251
* added missing angle bracket by @toolittlecakes in https://github.com/jxnl/instructor/pull/252
* Small doc fix for FastAPI section by @waseemhnyc in https://github.com/jxnl/instructor/pull/253

## New Contributors
* @toolittlecakes made their first contribution in https://github.com/jxnl/instructor/pull/251
* @waseemhnyc made their first contribution in https://github.com/jxnl/instructor/pull/253

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.4.1...0.4.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.4.2)

---

## 0.4.1: 0.4.1
**Published:** 2023-12-04

## What's Changed
* Fixed up missing dependencies and updated README.md by @ivanleomk in https://github.com/jxnl/instructor/pull/232
* generator blog post by @Anmol6 in https://github.com/jxnl/instructor/pull/230
* Update caching.md by @MeDott29 in https://github.com/jxnl/instructor/pull/233
* Adding Open Router inference Example by @PhiBrandon in https://github.com/jxnl/instructor/pull/226
* add: fastpi to concepts by @Muhtasham in https://github.com/jxnl/instructor/pull/234
* Generator blog: small formatting by @Anmol6 in https://github.com/jxnl/instructor/pull/237
* ref fastapi in generator.md by @Anmol6 in https://github.com/jxnl/instructor/pull/240
* Opensource examples by @PhiBrandon in https://github.com/jxnl/instructor/pull/238
* Fixed 1 spelling error in docs by @AlexTelon in https://github.com/jxnl/instructor/pull/236
* chore: add grit pattern enforcement by @morgante in https://github.com/jxnl/instructor/pull/243
* Fix #244 -- Refactor dump_message function to force content key  by @Guiforge in https://github.com/jxnl/instructor/pull/245
* Markdown JSON Mode by @Anmol6 in https://github.com/jxnl/instructor/pull/246
* Documentation: Update planning-tasks.md by @taziksh in https://github.com/jxnl/instructor/pull/250

## New Contributors
* @PhiBrandon made their first contribution in https://github.com/jxnl/instructor/pull/226
* @Muhtasham made their first contribution in https://github.com/jxnl/instructor/pull/234
* @AlexTelon made their first contribution in https://github.com/jxnl/instructor/pull/236
* @morgante made their first contribution in https://github.com/jxnl/instructor/pull/243
* @Guiforge made their first contribution in https://github.com/jxnl/instructor/pull/245
* @taziksh made their first contribution in https://github.com/jxnl/instructor/pull/250

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.4.0...0.4.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.4.1)

---

## 0.4.0: 0.4.0
**Published:** 2023-11-27

Many Improvements were made:

1. Multitask is swapped with Iterable[T]
2. More validations like content moderation
3. Supporting tool_call and JSON_MODE via the Mode patch.

## What's Changed
* small fixes to tutorials by @fpingham in https://github.com/jxnl/instructor/pull/168
* first version validation tutorial by @fpingham in https://github.com/jxnl/instructor/pull/180
* Tutorials creative acts in documentation by @MeDott29 in https://github.com/jxnl/instructor/pull/191
* Update index.md by @OxfordOutlander in https://github.com/jxnl/instructor/pull/199
* Add coveralls by @jxnl in https://github.com/jxnl/instructor/pull/203
* Ivan/tutorial cod by @ivanleomk in https://github.com/jxnl/instructor/pull/193
* small fixes to tutorials by @fpingham in https://github.com/jxnl/instructor/pull/205
* Minor corrections to jupyter notebooks by @aastroza in https://github.com/jxnl/instructor/pull/206
* Openai mod validator by @fpingham in https://github.com/jxnl/instructor/pull/207
* doc: add missing imports to some examples in README.md by @tavisrudd in https://github.com/jxnl/instructor/pull/215
* Add multiple modalities: tools, functions, json_mode by @jxnl in https://github.com/jxnl/instructor/pull/218
* Blog: Mastering Caching  by @jxnl in https://github.com/jxnl/instructor/pull/219
* Split coverage by @jxnl in https://github.com/jxnl/instructor/pull/222
* Add client test fixtures by @jxnl in https://github.com/jxnl/instructor/pull/227
* Support Streaming MultiTask with response_model by @Anmol6 in https://github.com/jxnl/instructor/pull/221
* Add braintrust proxy by @ankrgyl in https://github.com/jxnl/instructor/pull/225

## New Contributors
* @OxfordOutlander made their first contribution in https://github.com/jxnl/instructor/pull/199
* @aastroza made their first contribution in https://github.com/jxnl/instructor/pull/206
* @tavisrudd made their first contribution in https://github.com/jxnl/instructor/pull/215
* @Anmol6 made their first contribution in https://github.com/jxnl/instructor/pull/221
* @ankrgyl made their first contribution in https://github.com/jxnl/instructor/pull/225

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.3.5...0.4.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.4.0)

---

## 0.3.5: 0.3.5
**Published:** 2023-11-19

## What's Changed
* Spelling fix -  chain-of-density.md by @mitch-36 in https://github.com/jxnl/instructor/pull/176
* Fix llm_validator by @jxnl in https://github.com/jxnl/instructor/pull/179
* Fix async usage by @Omegastick in https://github.com/jxnl/instructor/pull/167
* Fix syntax error in code example by @smuotoe in https://github.com/jxnl/instructor/pull/182
* Blog on learning some async options by @jxnl in https://github.com/jxnl/instructor/pull/177
* improve documentation Readme by @jxnl in https://github.com/jxnl/instructor/pull/186
* Correct typo by @daaniyaan in https://github.com/jxnl/instructor/pull/170
* Creative acts in documentation by @MeDott29 in https://github.com/jxnl/instructor/pull/188
* Improve Documentation by @jxnl in https://github.com/jxnl/instructor/pull/189
* Add tutorials  by @jxnl in https://github.com/jxnl/instructor/pull/154
* Examples of using LLMs for citation verification by @jxnl in https://github.com/jxnl/instructor/pull/192
* Update 2.tips.ipynb by @daaniyaan in https://github.com/jxnl/instructor/pull/194
* RFC how much detail is too much?  by @MeDott29 in https://github.com/jxnl/instructor/pull/198

## New Contributors
* @mitch-36 made their first contribution in https://github.com/jxnl/instructor/pull/176
* @Omegastick made their first contribution in https://github.com/jxnl/instructor/pull/167
* @smuotoe made their first contribution in https://github.com/jxnl/instructor/pull/182

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.3.4...0.3.5

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.3.5)

---

## 0.3.4: 0.3.4
**Published:** 2023-11-13

## What's Changed
* Fix typo by @Xeophon in https://github.com/jxnl/instructor/pull/173
* fixes retry_async message unpacking by @bradenkinard in https://github.com/jxnl/instructor/pull/175

## New Contributors
* @Xeophon made their first contribution in https://github.com/jxnl/instructor/pull/173
* @bradenkinard made their first contribution in https://github.com/jxnl/instructor/pull/175

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.3.3...0.3.4

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.3.4)

---

## 0.3.3: 0.3.3
**Published:** 2023-11-13

## What's Changed
* Added support for model suffix and added migrations for new OpenAI SDK by @ivanleomk in https://github.com/jxnl/instructor/pull/169
* Chain of density by @ivanleomk in https://github.com/jxnl/instructor/pull/135
* Chain of density edits by @ivanleomk in https://github.com/jxnl/instructor/pull/171


**Full Changelog**: https://github.com/jxnl/instructor/compare/0.3.2...0.3.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.3.3)

---

## 0.3.2: 0.3.2
**Published:** 2023-11-11

## What's Changed
* small typo fix by @bnkc in https://github.com/jxnl/instructor/pull/160
* Fix apatch by @jxnl in https://github.com/jxnl/instructor/pull/165

## New Contributors
* @bnkc made their first contribution in https://github.com/jxnl/instructor/pull/160

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.3.1...0.3.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.3.2)

---

## 0.3.1: 0.3.1
**Published:** 2023-11-09

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.3.0...0.3.1

FIxed issues with classmethod

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.3.1)

---

## 0.3.0: 0.3.0
**Published:** 2023-11-08

## Upgrading to openai 1.1.0

## Usage

```py hl_lines="5 13"
from openai import OpenAI()
import instructor

# Enables `response_model`
client = instructor.patch(OpenAI())

class UserDetail(BaseModel):
    name: str
    age: int

user = client.chat.completions.create(
    model="gpt-3.5-turbo",
    response_model=UserDetail,
    messages=[
        {"role": "user", "content": "Extract Jason is 25 years old"},
    ]
)

assert isinstance(user, UserDetail)
assert user.name == "Jason"
assert user.age == 25
```

##  note "Using `openai<1.0.0`"

  If you're using `openai<1.0.0` then make sure you `pip install instructor<0.3.0`
  where you can patch a global client like so:

  ```python hl_lines="4 8"
  import openai
  import instructor

  instructor.patch()

  user = openai.ChatCompletion.create(
      ...,
      response_model=UserDetail,
)
```

## What's Changed
* Migration to OpenAI 1.1.0 by @grit-app in https://github.com/jxnl/instructor/pull/152

## New Contributors
* @grit-app made their first contribution in https://github.com/jxnl/instructor/pull/152

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.2.11...0.3.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.3.0)

---

## 0.3.0rc: 0.3.0rc
**Published:** 2023-11-07
**Pre-release**

Release candidate for OpenAI 1.0

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.2.11...0.3.0rc

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.3.0rc)

---

## 0.2.11: 0.2.11
**Published:** 2023-11-06

## What's Changed
* Add File Validation and Hyperparameters Support to CLI by @daaniyaan in https://github.com/jxnl/instructor/pull/151

## Typos 
* fix end quote on model by @rgbkrk in https://github.com/jxnl/instructor/pull/141
* Include missing quote in function_calls.py by @rgbkrk in https://github.com/jxnl/instructor/pull/142
* fix typo in Validator by @pablopalafox in https://github.com/jxnl/instructor/pull/144
* Fix example link by @maxjeblick in https://github.com/jxnl/instructor/pull/147

## New Contributors
* @rgbkrk made their first contribution in https://github.com/jxnl/instructor/pull/141
* @pablopalafox made their first contribution in https://github.com/jxnl/instructor/pull/144
* @maxjeblick made their first contribution in https://github.com/jxnl/instructor/pull/147
* @daaniyaan made their first contribution in https://github.com/jxnl/instructor/pull/151

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.2.10...0.2.11

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.11)

---

## 0.2.10: 0.2.10
**Published:** 2023-11-04

## What's Changed
* Blog post: Validation is Validation by @jxnl in https://github.com/jxnl/instructor/pull/121
* Update README.md typo by @jeff3071 in https://github.com/jxnl/instructor/pull/124
* Validation part 1 proposed edits by @ivanleomk in https://github.com/jxnl/instructor/pull/125
* Remove openaischema from index.md by @jxnl in https://github.com/jxnl/instructor/pull/129
* Updated Distillation Article with some added points by @ivanleomk in https://github.com/jxnl/instructor/pull/131
* Update hash of requirements by @jxnl in https://github.com/jxnl/instructor/pull/137
* Azure support multitask.py by @zboyles in https://github.com/jxnl/instructor/pull/136

## New Contributors
* @jeff3071 made their first contribution in https://github.com/jxnl/instructor/pull/124
* @zboyles made their first contribution in https://github.com/jxnl/instructor/pull/136

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.2.9...0.2.10

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.10)

---

## 0.2.9: 0.2.9
**Published:** 2023-10-22

## What's Changed
* Expose unpatch() function by @NISH1001 in https://github.com/jxnl/instructor/pull/114
* Implementing the Distillation Decorator by @jxnl in https://github.com/jxnl/instructor/pull/118
* Pass strict through from create to from_response by @jxnl in https://github.com/jxnl/instructor/pull/119

## New Contributors
* @NISH1001 made their first contribution in https://github.com/jxnl/instructor/pull/114

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.2.8...0.2.9

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.9)

---

## 0.2.8: 0.2.8
**Published:** 2023-09-26

## What's Changed
* Reasking logic on validations  by @jxnl in https://github.com/jxnl/instructor/pull/98
* better docs for reasking by @jxnl in https://github.com/jxnl/instructor/pull/99
* Implement validation context by @jxnl in https://github.com/jxnl/instructor/pull/100
* Blog post for Search by @jxnl in https://github.com/jxnl/instructor/pull/105
* Rag Blog Feedback by @jxnl in https://github.com/jxnl/instructor/pull/106
* Minor edits by @amorriscode in https://github.com/jxnl/instructor/pull/107
* Chain of density in examples  by @jxnl in https://github.com/jxnl/instructor/pull/110
* Fix MkDocs Build in CI Pipeline by @jlondonobo in https://github.com/jxnl/instructor/pull/108
* Add minify plugin to requirements-doc.txt by @jlondonobo in https://github.com/jxnl/instructor/pull/111
* Install `pngquant` in MkDocs Pipeline for correct image optimization by @jlondonobo in https://github.com/jxnl/instructor/pull/112

## New Contributors
* @amorriscode made their first contribution in https://github.com/jxnl/instructor/pull/107
* @jlondonobo made their first contribution in https://github.com/jxnl/instructor/pull/108

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.2.7...0.2.8

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.8)

---

## 0.2.7: 0.2.7
**Published:** 2023-09-08

## What's Changed
* Maybe helper to dynamically create a class with errors on extraction by @jxnl in https://github.com/jxnl/instructor/pull/95
* Improve Documentation by @jxnl in https://github.com/jxnl/instructor/pull/96
* Implement Simple Validators  by @jxnl in https://github.com/jxnl/instructor/pull/97


**Full Changelog**: https://github.com/jxnl/instructor/compare/0.2.6...0.2.7

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.7)

---

## 0.2.6: 0.2.6
**Published:** 2023-09-06

## What's Changed
* Add citations examples by @jxnl in https://github.com/jxnl/instructor/pull/88
* fix fine-tune CLI readme formatting by @dhruv-anand-aintech in https://github.com/jxnl/instructor/pull/89
* Upgrade typer by @jxnl in https://github.com/jxnl/instructor/pull/90
* Improve some prompt engineering tips by @jxnl in https://github.com/jxnl/instructor/pull/91
* Usage CLI by @jxnl in https://github.com/jxnl/instructor/pull/93

## New Contributors
* @dhruv-anand-aintech made their first contribution in https://github.com/jxnl/instructor/pull/89

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.2.5...0.2.6

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.6)

---

## 0.2.5: 0.2.5
**Published:** 2023-08-24

## What's Changed
* update message assignment by @neilneuwirth in https://github.com/jxnl/instructor/pull/80
* Implement CLI for finetuning by @jxnl in https://github.com/jxnl/instructor/pull/85
* Docstring parsing by @AIexanderDicke in https://github.com/jxnl/instructor/pull/83

## New Contributors
* @neilneuwirth made their first contribution in https://github.com/jxnl/instructor/pull/80
* @AIexanderDicke made their first contribution in https://github.com/jxnl/instructor/pull/76

**Full Changelog**: https://github.com/jxnl/instructor/compare/0.2.4...0.2.5

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.5)

---

## 0.2.4: 0.2.4
**Published:** 2023-08-17

## What's Changed
* Rename to Instructor by @jxnl in https://github.com/jxnl/instructor/pull/79


**Full Changelog**: https://github.com/jxnl/instructor/compare/0.2.3...0.2.4

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.4)

---

## 0.2.3: 0.2.3
**Published:** 2023-08-16

## What's Changed
* Support patching openai by @jxnl in https://github.com/jxnl/openai_function_call/pull/78


**Full Changelog**: https://github.com/jxnl/openai_function_call/compare/0.2.2...0.2.3

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.3)

---

## 0.2.2: 0.2.2
**Published:** 2023-07-31

## What's Changed
* Streaming app by @jxnl in https://github.com/jxnl/openai_function_call/pull/72
* Allow less strict JSON parsing by @samiur in https://github.com/jxnl/openai_function_call/pull/75
* Excluding properties with defaults from required as per issue #41 by @KoljaB in https://github.com/jxnl/openai_function_call/pull/74

## New Contributors
* @samiur made their first contribution in https://github.com/jxnl/openai_function_call/pull/75
* @KoljaB made their first contribution in https://github.com/jxnl/openai_function_call/pull/74

**Full Changelog**: https://github.com/jxnl/openai_function_call/compare/0.2.1...0.2.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.2)

---

## 0.2.1: 0.2.1
**Published:** 2023-07-22

## What's Changed
* Implement streaming entities via MultiTask by @jxnl in https://github.com/jxnl/openai_function_call/pull/64
* Add refactoring example to gpt-engineer by @cristobalcl in https://github.com/jxnl/openai_function_call/pull/61
* Small typo in readme by @bllchmbrs in https://github.com/jxnl/openai_function_call/pull/69
* Update mkdocs ci by @DaveOkpare in https://github.com/jxnl/openai_function_call/pull/67

## New Contributors
* @bllchmbrs made their first contribution in https://github.com/jxnl/openai_function_call/pull/69

**Full Changelog**: https://github.com/jxnl/openai_function_call/compare/0.2.0...0.2.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.1)

---

## 0.2.0: 0.2.0
**Published:** 2023-07-17

## What's Changed
* Upgrade to pydanticv2 by @jxnl in https://github.com/jxnl/openai_function_call/pull/63


**Full Changelog**: https://github.com/jxnl/openai_function_call/compare/0.1.2...0.2.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.2.0)

---

## 0.1.2: 0.1.2
**Published:** 2023-07-17

## What's Changed
* Better default descriptions by @jxnl in https://github.com/jxnl/openai_function_call/pull/62


**Full Changelog**: https://github.com/jxnl/openai_function_call/compare/0.1.1...0.1.2

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.1.2)

---

## 0.1.1: 0.1.1
**Published:** 2023-07-14

## What's Changed
* Improve doc configs w/ line highlights by @jxnl in https://github.com/jxnl/openai_function_call/pull/48
* typo readme DSL example by @adriangalilea in https://github.com/jxnl/openai_function_call/pull/50
* Add python 3.11 to test matrix by @awtkns in https://github.com/jxnl/openai_function_call/pull/51
* Minor fixes on docs/index.md by @DaveOkpare in https://github.com/jxnl/openai_function_call/pull/57
* Fix typos by @DaveOkpare in https://github.com/jxnl/openai_function_call/pull/58
* Completion create function returns openai completion if there is no f… by @Phodaie in https://github.com/jxnl/openai_function_call/pull/56
* fix: update variable name in from_response example by @marcosmagallanes in https://github.com/jxnl/openai_function_call/pull/59
* fixed docstring typos by @fpingham in https://github.com/jxnl/openai_function_call/pull/60
* Add documentation for multi file programs by @DaveOkpare in https://github.com/jxnl/openai_function_call/pull/52

## New Contributors
* @adriangalilea made their first contribution in https://github.com/jxnl/openai_function_call/pull/50
* @awtkns made their first contribution in https://github.com/jxnl/openai_function_call/pull/51
* @Phodaie made their first contribution in https://github.com/jxnl/openai_function_call/pull/56
* @marcosmagallanes made their first contribution in https://github.com/jxnl/openai_function_call/pull/59

**Full Changelog**: https://github.com/jxnl/openai_function_call/compare/0.1.0...0.1.1

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.1.1)

---

## 0.1.0: Prompting DSL with Documentation
**Published:** 2023-07-09

## What's Changed
* Installed erdantic and added schemas  by @DaveOkpare in https://github.com/jxnl/openai_function_call/pull/20
* No exp by @jxnl in https://github.com/jxnl/openai_function_call/pull/26
* Experimental Prompting DSL by @jxnl in https://github.com/jxnl/openai_function_call/pull/25
* fixed completions endpoint and readme details for dsl example by @fpingham in https://github.com/jxnl/openai_function_call/pull/33
* Added openai_schema decorator by @DaveOkpare in https://github.com/jxnl/openai_function_call/pull/34
* GitHub Action for testing by @cristobalcl in https://github.com/jxnl/openai_function_call/pull/38
* warning for v > 3.9, correct package name. by @zShanCS in https://github.com/jxnl/openai_function_call/pull/43
* Docs! Help wanted, adding examples. by @jxnl in https://github.com/jxnl/openai_function_call/pull/44
* Attempt to support DSL by @jxnl in https://github.com/jxnl/openai_function_call/pull/45

## New Contributors
* @cristobalcl made their first contribution in https://github.com/jxnl/openai_function_call/pull/38
* @zShanCS made their first contribution in https://github.com/jxnl/openai_function_call/pull/43

**Full Changelog**: https://github.com/jxnl/openai_function_call/compare/0.0.5...0.1.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.1.0)

---

## 0.1.0rc: Add support for DSL
**Published:** 2023-07-08
**Pre-release**

In this release we have some more documentation and included a preliminary version of the DSL and also some documentation thanks for mkdoc

In the 0.1.x release we hope to release more documentation around using the DSL and a library of examples to get people's creative  juices flowing. 

## What's Changed
* Experimental Prompting DSL by @jxnl in https://github.com/jxnl/openai_function_call/pull/25
* fixed completions endpoint and readme details for dsl example by @fpingham in https://github.com/jxnl/openai_function_call/pull/33
* Added openai_schema decorator by @DaveOkpare in https://github.com/jxnl/openai_function_call/pull/34
* GitHub Action for testing by @cristobalcl in https://github.com/jxnl/openai_function_call/pull/38
* warning for v > 3.9, correct package name. by @zShanCS in https://github.com/jxnl/openai_function_call/pull/43
* Docs! Help wanted, adding examples. by @jxnl in https://github.com/jxnl/openai_function_call/pull/44
* Attempt to support DSL by @jxnl in https://github.com/jxnl/openai_function_call/pull/45

## New Contributors
* @cristobalcl made their first contribution in https://github.com/jxnl/openai_function_call/pull/38
* @zShanCS made their first contribution in https://github.com/jxnl/openai_function_call/pull/43

**Full Changelog**: https://github.com/jxnl/openai_function_call/compare/0.0.5...0.1.0

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.1.0rc)

---

## 0.0.5: 0.0.5
**Published:** 2023-06-23

## What's Changed
* Add repository link to pyproject.toml by @jxnl in https://github.com/jxnl/openai_function_call/pull/23


**Full Changelog**: https://github.com/jxnl/openai_function_call/compare/0.0.4...0.0.5

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.0.5)

---

## 0.0.4: 0.0.4
**Published:** 2023-06-23

**Full Changelog**: https://github.com/jxnl/openai_function_call/compare/0.0.3...0.0.4

Updated readme.

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.0.4)

---

## 0.0.3: 0.0.3
**Published:** 2023-06-23

Initial release on github! 

[View on GitHub](https://github.com/567-labs/instructor/releases/tag/0.0.3)

---

