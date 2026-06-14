from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from app.assessor import extract_score_context, normalize_report_data, soft_missing_labels, validate_profile
from app.documents import Chunk, build_chunks, parse_front_matter, split_text
from app.ingest import html_to_markdown, ingest_sources
from app.models import ApplicantPath, ApplicantProfile, AssessRequest, AssessmentReport, FitLevel
from app.retrieval import HybridRetriever, VectorIndex, reciprocal_rank_fusion, result_to_source
from app.sources import OfficialSource


class IngestTests(unittest.TestCase):
    def test_html_to_markdown_extracts_title_and_table(self) -> None:
        source = OfficialSource("demo", "Demo Title", "https://example.com", "测试", "all")
        html = """
        <html><head><title>Ignored</title></head>
        <body><article><h1>招生章程</h1><p>第一段内容。</p>
        <table><tr><th>项目</th><th>金额</th></tr><tr><td>学费</td><td>人民币</td></tr></table>
        <script>bad()</script></article></body></html>
        """
        markdown = html_to_markdown(html, source)
        self.assertIn("# 招生章程", markdown)
        self.assertIn("第一段内容", markdown)
        self.assertIn("项目 | 金额", markdown)
        self.assertNotIn("bad()", markdown)

    def test_front_matter_parser(self) -> None:
        raw = '---\ntitle: "标题"\nurl: "https://example.com"\n---\n\n# 正文'
        metadata, body = parse_front_matter(raw)
        self.assertEqual(metadata["title"], "标题")
        self.assertEqual(metadata["url"], "https://example.com")
        self.assertIn("正文", body)


class DocumentTests(unittest.TestCase):
    def test_split_text_keeps_chunks_with_overlap(self) -> None:
        text = "第一段内容。" * 80
        chunks = split_text(text, chunk_size=120, chunk_overlap=20)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 140 for chunk in chunks))

    def test_build_chunks_adds_metadata(self) -> None:
        from app.documents import Document

        documents = [
            Document(
                path="demo.md",
                title="Demo",
                source_id="demo",
                url="https://example.com",
                category="测试",
                applicant_path="all",
                text="这是测试内容。" * 30,
            )
        ]
        chunks = build_chunks(documents, chunk_size=80, chunk_overlap=10)
        self.assertEqual(chunks[0].title, "Demo")
        self.assertEqual(chunks[0].url, "https://example.com")


class RetrievalTests(unittest.TestCase):
    def make_chunk(self, chunk_id: int, text: str) -> Chunk:
        return Chunk(
            chunk_id=chunk_id,
            text=text,
            source_id=f"s{chunk_id}",
            title=f"title {chunk_id}",
            url=f"https://example.com/{chunk_id}",
            category="测试",
            applicant_path="all",
            path=f"{chunk_id}.md",
        )

    def test_rrf_combines_ranked_lists(self) -> None:
        first = self.make_chunk(0, "高考 招生")
        second = self.make_chunk(1, "学费 住宿")
        fused = reciprocal_rank_fusion(
            [
                [{"rank": 1, "score": 0.9, "chunk": first}],
                [{"rank": 1, "score": 3.0, "chunk": second}, {"rank": 2, "score": 2.0, "chunk": first}],
            ],
            top_k=2,
        )
        self.assertEqual(len(fused), 2)
        self.assertIn(fused[0]["chunk"].chunk_id, {0, 1})

    def test_hybrid_retriever_returns_sources(self) -> None:
        chunks = [
            self.make_chunk(0, "高考 招生 英语 成绩"),
            self.make_chunk(1, "学费 住宿费 奖学金"),
        ]
        index = VectorIndex(np.array([[0.0, 0.0], [1.0, 1.0]], dtype="float32"), chunks)
        retriever = HybridRetriever(index)
        results = retriever.search("高考 英语", [0.0, 0.1], top_k=2)
        source = result_to_source(results[0])
        self.assertIn("title", source)
        self.assertIn("text", source)


class IngestFaultToleranceTests(unittest.TestCase):
    def make_source(self, source_id: str, url: str = "https://example.com") -> OfficialSource:
        return OfficialSource(source_id, "Title " + source_id, url, "测试", "all")

    def test_continues_after_failure(self) -> None:
        """Even when one source fails, subsequent sources are still fetched."""
        sources = [
            self.make_source("bad", "https://fail.example.com"),
            self.make_source("good", "https://example.com"),
        ]
        call_order: list[str] = []

        def fake_fetch(url: str, timeout: int = 30) -> str:
            call_order.append(url)
            if "fail" in url:
                raise RuntimeError("模拟网络错误")
            return "<html><body><h1>Good</h1><p>Content.</p></body></html>"

        with patch("app.ingest.fetch_html", side_effect=fake_fetch):
            result = ingest_sources(sources)

        self.assertEqual(len(result["ingested"]), 1)
        self.assertEqual(result["ingested"][0]["source_id"], "good")
        self.assertEqual(len(result["failed"]), 1)
        self.assertEqual(result["failed"][0]["source_id"], "bad")
        self.assertIn("模拟网络错误", result["failed"][0]["error"])
        self.assertEqual(call_order, ["https://fail.example.com", "https://example.com"])

    def test_all_fail_returns_empty_results(self) -> None:
        """When every source fails, ingested is empty but no exception is raised."""
        sources = [
            self.make_source("a"),
            self.make_source("b"),
        ]

        def fake_fetch(url: str, timeout: int = 30) -> str:
            raise RuntimeError("网络不可用")

        with patch("app.ingest.fetch_html", side_effect=fake_fetch):
            result = ingest_sources(sources)

        self.assertEqual(len(result["ingested"]), 0)
        self.assertEqual(len(result["failed"]), 2)


class AssessmentTests(unittest.TestCase):
    def complete_profile(self) -> ApplicantProfile:
        return ApplicantProfile(
            applicant_path=ApplicantPath.mainland_gaokao,
            region="广东",
            exam_type="高考",
            score_summary="总分较高，省排名靠前",
            english_level="高考英语 135",
            intended_major="数据科学",
            competitions_projects="数学竞赛省奖",
            budget="可承担学费住宿费",
            adaptability="能接受英文教学",
            constraints="希望留在大湾区",
        )

    def test_validate_profile_finds_missing_fields(self) -> None:
        profile = ApplicantProfile(applicant_path=ApplicantPath.international)
        hard_missing = validate_profile(profile)
        # Hard-required fields: region, exam_type, score_summary, intended_major
        self.assertIn("成绩/排名/等级", hard_missing)
        self.assertIn("意向专业", hard_missing)
        self.assertIn("地区/省份/国家", hard_missing)
        self.assertIn("考试类型", hard_missing)
        self.assertEqual(len(hard_missing), 4)  # Only hard-required, no soft fields

    def test_soft_missing_excludes_hard_required_fields(self) -> None:
        profile = ApplicantProfile(applicant_path=ApplicantPath.international)
        soft = soft_missing_labels(profile)
        # english_level, budget, adaptability are soft — missing here
        self.assertIn("英语能力", soft)
        self.assertIn("预算情况", soft)
        self.assertIn("适应能力", soft)
        # But region, exam_type etc. are hard — not reported here
        self.assertNotIn("地区/省份/国家", soft)
        self.assertNotIn("成绩/排名/等级", soft)

    def test_full_profile_passes_validation(self) -> None:
        profile = self.complete_profile()
        hard_missing = validate_profile(profile)
        self.assertEqual(len(hard_missing), 0)
        soft = soft_missing_labels(profile)
        self.assertEqual(len(soft), 0)

    def test_normalize_report_data_guards_bad_level(self) -> None:
        data = normalize_report_data({"fit_level": "录取概率90%", "conclusion": "测试"})
        self.assertEqual(data["fit_level"], FitLevel.conditional_fit.value)

    def test_assess_endpoint_logic_with_mock_llm(self) -> None:
        import app.main as main

        chunk = Chunk(
            chunk_id=0,
            text="官方资料片段：招生要求。",
            source_id="demo",
            title="官方资料",
            url="https://example.com",
            category="招生章程",
            applicant_path="mainland_gaokao",
            path="demo.md",
        )

        class FakeRetriever:
            def search(self, query, query_vector, top_k):
                return [{"score": 0.2, "chunk": chunk}]

        report = AssessmentReport(
            fit_level=FitLevel.conditional_fit,
            conclusion="可以申请，但需要继续核对官方要求。",
            key_evidence=["来自官方资料"],
        )

        with patch.object(main, "retriever", FakeRetriever()), \
            patch.object(main, "ollama_embed", return_value=[[0.1, 0.2]]), \
            patch.object(main, "call_llm_for_report", return_value=report), \
            patch.object(main, "append_history") as append_history:
            response = main.assess(AssessRequest(profile=self.complete_profile(), save_history=True))

        self.assertEqual(response.status, "ok")
        self.assertEqual(response.report.fit_level, FitLevel.conditional_fit)
        append_history.assert_called_once()

    # ── extract_score_context tests ──

    def test_extract_score_context_finds_tianjin_line(self) -> None:
        """When sources contain Tianjin's 2025 score line, it should be extracted."""
        sources = [
            {
                "title": "录取分数线",
                "url": "https://example.com",
                "text": "| 天津 | 综合改革 | 652 | - |",
            }
        ]
        result = extract_score_context(sources, region="天津")
        self.assertIn("天津", result)
        self.assertIn("652", result)

    def test_extract_score_context_finds_national_stats(self) -> None:
        """National statistics should be extracted when available."""
        sources = [
            {
                "title": "统计数据",
                "url": "https://example.com",
                "text": (
                    "物理类/选考最低录取分稳居各省市考生前 2% 以内。"
                    "录取学生高考英语平均分高达 136 分。"
                ),
            }
        ]
        result = extract_score_context(sources, region="西藏")
        self.assertIn("前2%", result)
        self.assertIn("136", result)

    def test_extract_score_context_returns_fallback_when_no_province_found(self) -> None:
        """When no province match exists, the fallback message should appear."""
        sources = [
            {
                "title": "其他内容",
                "url": "https://example.com",
                "text": "This text contains no Chinese province score lines at all.",
            }
        ]
        result = extract_score_context(sources, region="火星")
        self.assertIn("未在检索片段中找到", result)

    def test_extract_score_context_includes_neighbour_provinces(self) -> None:
        """Neighbour province score lines should appear as cross-reference."""
        sources = [
            {
                "title": "分数线",
                "url": "https://example.com",
                "text": (
                    "| 天津 | 综合改革 | 652 | - |\n"
                    "| 北京 | 综合改革（不限） | 644 | 3976 |\n"
                    "| 河北 | 物理类 | 639 | - |\n"
                ),
            }
        ]
        result = extract_score_context(sources, region="天津")
        self.assertIn("天津", result)
        self.assertIn("652", result)
        self.assertIn("毗邻/同类省份参考", result)


if __name__ == "__main__":
    unittest.main()
