from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from app.assessor import normalize_report_data, validate_profile
from app.documents import Chunk, build_chunks, parse_front_matter, split_text
from app.ingest import html_to_markdown
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
        missing = validate_profile(profile)
        self.assertIn("成绩/排名/等级", missing)
        self.assertIn("英语能力", missing)

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


if __name__ == "__main__":
    unittest.main()
