from backend.orchestrator.market_scout_citations import append_market_scout_sources, market_scout_source_suffix


def test_appends_market_scout_sources_to_final_answer() -> None:
    answer = append_market_scout_sources("Cloud engineering has strong potential.", [_tool_call()])

    assert "Nguồn tham khảo:" in answer
    assert "[TopDev - Cloud outlook](https://topdev.vn/cloud-outlook)" in answer
    assert "[ILO - Jobs outlook](https://ilo.org/jobs-outlook)" in answer


def test_does_not_duplicate_sources_already_in_source_section() -> None:
    answer = (
        "Cloud engineering has strong potential.\n\n"
        "Nguồn tham khảo:\n"
        "- [TopDev - Cloud outlook](https://topdev.vn/cloud-outlook)"
    )

    suffix = market_scout_source_suffix(answer, [_tool_call()])

    assert "https://topdev.vn/cloud-outlook" not in suffix
    assert "[ILO - Jobs outlook](https://ilo.org/jobs-outlook)" in suffix


def test_ignores_non_market_scout_tool_calls() -> None:
    assert append_market_scout_sources("Answer.", [{"name": "profile_scanner", "output": {}}]) == "Answer."


def test_deduplicates_urls_and_limits_sources_to_five() -> None:
    sources = [
        {"publisher": "Publisher", "source_name": f"Source {index}", "url": f"https://example.com/{index}"}
        for index in range(6)
    ]
    sources.append(dict(sources[0]))

    answer = append_market_scout_sources("Answer.", [{"name": "market_scout", "output": {"sources": sources}}])

    assert answer.count("https://") == 5


def test_reads_mcp_text_content_blocks() -> None:
    tool_call = _tool_call()
    tool_call["output"] = [{"type": "text", "text": '{"sources":[{"publisher":"ILO","source_name":"Report","url":"https://ilo.org/report"}]}'}]

    answer = append_market_scout_sources("Answer.", [tool_call])

    assert "[ILO - Report](https://ilo.org/report)" in answer


def test_deduplicates_existing_markdown_link_with_tracking_variants() -> None:
    answer = (
        "Both roles have potential.\n\n"
        "Nguồn tham khảo:\n"
        "- [TopDev - Comparison](https://topdev.vn/compare-role/)"
    )
    tool_call = {
        "name": "market_scout",
        "output": {
            "sources": [
                {
                    "publisher": "TopDev",
                    "source_name": "Comparison",
                    "url": "https://topdev.vn/compare-role?utm_source=tavily",
                },
                {
                    "publisher": "TopDev",
                    "source_name": "Comparison duplicate",
                    "url": "https://topdev.vn/compare-role#summary",
                },
            ]
        },
    }

    assert market_scout_source_suffix(answer, [tool_call]) == ""


def test_deduplicates_same_source_label_with_different_urls() -> None:
    tool_call = {
        "name": "market_scout",
        "output": {
            "sources": [
                {"publisher": "TopDev", "source_name": "Role comparison", "url": "https://topdev.vn/article/1"},
                {"publisher": "TopDev", "source_name": "Role comparison", "url": "https://topdev.vn/article/2"},
            ]
        },
    }

    answer = append_market_scout_sources("Answer.", [tool_call])

    assert answer.count("TopDev - Role comparison") == 1


def _tool_call() -> dict:
    return {
        "name": "market_scout",
        "output": {
            "sources": [
                {
                    "publisher": "TopDev",
                    "source_name": "Cloud outlook",
                    "url": "https://topdev.vn/cloud-outlook",
                },
                {
                    "publisher": "ILO",
                    "source_name": "Jobs outlook",
                    "url": "https://ilo.org/jobs-outlook",
                },
            ]
        },
    }
