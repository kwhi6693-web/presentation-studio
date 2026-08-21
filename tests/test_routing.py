from __future__ import annotations

import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "presentation-studio"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_ROOT))

from core import retrieval
from core.catalog import CatalogError, validate_products
from core.request import Request, normalize_request
from core.retrieval import _tokens, recommend_product
from core.router import route_request


class PartialEditabilityTests(unittest.TestCase):
    def test_cli_entrypoints_do_not_create_bytecode_cache_in_skill_tree(self) -> None:
        scripts = ("recommend.py", "route.py", "validate_manifest.py")
        for script in scripts:
            with self.subTest(script=script):
                subprocess.run(
                    [sys.executable, str(SKILL_ROOT / "scripts" / script), "--help"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
        cache_directories = tuple(SKILL_ROOT.rglob("__pycache__"))
        self.assertEqual(cache_directories, ())

    def setUp(self) -> None:
        self.request = {
            "kind": "presentation",
            "outputs": ["pptx", "html", "pdf"],
            "editable": True,
            "has_exact_data": False,
            "topic": "AI product strategy",
            "audience": "executives",
            "purpose": "strategy briefing",
            "tone": "confident",
            "channel": "boardroom",
            "density": "medium",
            "assets": [],
            "data_forms": [],
            "readiness": {
                "python": True,
                "node": True,
                "pptx_core": True,
                "office_renderer": True,
                "chromium": True,
                "image_provider": False,
            },
        }

    def test_dual_format_product_satisfies_editability_via_pptx_output(self) -> None:
        recommendation = recommend_product(self.request)
        self.assertEqual(recommendation.status, "PASS")
        self.assertEqual(recommendation.product_id, "dual-format-deck")

        plan = route_request(
            {
                **self.request,
                "product": recommendation.product_id,
                "style": recommendation.style["selected"],
            }
        )
        self.assertEqual(plan.outputs, ("pptx", "html", "pdf"))
        self.assertEqual(plan.engines, ("ppt-master", "frontend-slides"))

    def test_editable_request_without_an_editable_requested_output_is_rejected(self) -> None:
        request = {**self.request, "outputs": ["html", "pdf"]}
        recommendation = recommend_product(request)
        self.assertEqual(recommendation.status, "FAIL")
        self.assertIsNone(recommendation.product_id)

    def test_exact_legacy_five_key_readiness_preserves_pptx_and_baoyu_products(self) -> None:
        readiness = {
            "python": True,
            "node": True,
            "office_renderer": False,
            "chromium": False,
            "image_provider": False,
        }
        self.assertEqual(
            set(readiness),
            {"python", "node", "office_renderer", "chromium", "image_provider"},
        )
        cases = (
            ({"kind": "presentation", "outputs": ["pptx"], "topic": "technical architecture"}, "ppt-master"),
            ({"kind": "cover", "outputs": ["png"], "topic": "article cover"}, "baoyu"),
        )
        for request, engine in cases:
            with self.subTest(engine=engine):
                recommendation = recommend_product({**request, "readiness": readiness})

                self.assertIsNotNone(recommendation.product_id)
                self.assertIn(engine, recommendation.engine_chain)
                self.assertEqual(recommendation.status, "PARTIAL")

    def test_exact_legacy_parent_runtime_false_cannot_assume_capability(self) -> None:
        cases = (
            (
                {"python": False, "node": True, "office_renderer": False, "chromium": False, "image_provider": False},
                {"kind": "presentation", "outputs": ["pptx"], "topic": "technical architecture"},
            ),
            (
                {"python": True, "node": False, "office_renderer": False, "chromium": False, "image_provider": False},
                {"kind": "cover", "outputs": ["png"], "topic": "article cover"},
            ),
        )
        for readiness, request in cases:
            with self.subTest(readiness=readiness):
                recommendation = recommend_product({**request, "readiness": readiness})

                self.assertEqual(recommendation.status, "FAIL")
                self.assertIsNone(recommendation.product_id)

    def test_modern_or_extended_readiness_never_backfills_missing_capability(self) -> None:
        legacy = {
            "python": True,
            "node": True,
            "office_renderer": False,
            "chromium": False,
            "image_provider": False,
        }
        cases = (
            (
                {**legacy, "pptx_core": True},
                {"kind": "cover", "outputs": ["png"], "topic": "article cover"},
                "baoyu_core",
            ),
            (
                {**legacy, "future_capability": True},
                {"kind": "presentation", "outputs": ["pptx"], "topic": "technical architecture"},
                "pptx_core",
            ),
        )
        for readiness, request, missing in cases:
            with self.subTest(readiness=readiness):
                recommendation = recommend_product({**request, "readiness": readiness})

                self.assertEqual(recommendation.status, "FAIL")
                self.assertIsNone(recommendation.product_id)
                self.assertIn(missing, recommendation.missing_prerequisites)

    def test_omitted_required_readiness_is_unknown_and_cannot_pass(self) -> None:
        recommendation = recommend_product(
            {
                "kind": "presentation",
                "outputs": ["pptx"],
                "topic": "technical architecture",
                "readiness": {"node": True},
            }
        )

        self.assertEqual(recommendation.status, "FAIL")
        self.assertIsNone(recommendation.product_id)
        self.assertIn("python", recommendation.missing_prerequisites)

    def test_unavailable_required_prerequisite_fails_without_a_runnable_fallback(self) -> None:
        recommendation = recommend_product(
            {
                "kind": "presentation",
                "outputs": ["pptx"],
                "topic": "technical architecture",
                "readiness": {
                    "python": False,
                    "node": True,
                    "pptx_core": True,
                    "office_renderer": True,
                },
            }
        )

        self.assertEqual(recommendation.status, "FAIL")
        self.assertIsNone(recommendation.product_id)
        self.assertIn("python", recommendation.missing_prerequisites)

    def test_generic_fallback_selects_optional_gap_product_as_partial(self) -> None:
        with tempfile.TemporaryDirectory(prefix="presentation-studio-fallback-") as directory:
            root = Path(directory)
            catalog = root / "catalog"
            catalog.mkdir()
            products = json.loads(
                (SKILL_ROOT / "catalog" / "products.json").read_text(encoding="utf-8")
            )
            source = next(product for product in products if product["id"] == "cover-image")
            fallback = json.loads(json.dumps(source))
            fallback.update(
                {
                    "id": "cover-runtime-fallback",
                    "intended_uses": ["fallback-cover"],
                    "required_prerequisites": ["node", "baoyu_core"],
                    "optional_prerequisites": ["chromium"],
                    "fallback": None,
                }
            )
            source.update(
                {
                    "id": "cover-runtime-source",
                    "intended_uses": ["runtime-source"],
                    "required_prerequisites": ["chromium", "baoyu_core"],
                    "optional_prerequisites": [],
                    "fallback": "cover-runtime-fallback",
                }
            )
            products.append(fallback)
            (catalog / "products.json").write_text(json.dumps(products), encoding="utf-8")
            (catalog / "styles.json").write_text(
                (SKILL_ROOT / "catalog" / "styles.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            recommendation = recommend_product(
                {
                    "kind": "cover",
                    "outputs": ["png"],
                    "topic": "runtime source",
                    "readiness": {"node": True, "baoyu_core": True, "chromium": False},
                },
                catalog_root=root,
            )

        self.assertEqual(recommendation.product_id, "cover-runtime-fallback")
        self.assertEqual(recommendation.fallback, "cover-runtime-fallback")
        self.assertEqual(recommendation.status, "PARTIAL")
        self.assertEqual(recommendation.missing_prerequisites, ("chromium",))

    def test_cyclic_fallback_chain_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="presentation-studio-fallback-cycle-") as directory:
            root = Path(directory)
            catalog = root / "catalog"
            catalog.mkdir()
            products = json.loads(
                (SKILL_ROOT / "catalog" / "products.json").read_text(encoding="utf-8")
            )
            source = next(product for product in products if product["id"] == "cover-image")
            fallback = json.loads(json.dumps(source))
            fallback.update(
                {
                    "id": "cover-cycle-fallback",
                    "intended_uses": ["fallback-cover"],
                    "required_prerequisites": ["node", "baoyu_core"],
                    "optional_prerequisites": [],
                    "fallback": "cover-cycle-source",
                }
            )
            source.update(
                {
                    "id": "cover-cycle-source",
                    "intended_uses": ["cycle-source"],
                    "required_prerequisites": ["chromium", "baoyu_core"],
                    "optional_prerequisites": [],
                    "fallback": "cover-cycle-fallback",
                }
            )
            products.append(fallback)
            (catalog / "products.json").write_text(json.dumps(products), encoding="utf-8")
            (catalog / "styles.json").write_text(
                (SKILL_ROOT / "catalog" / "styles.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            recommendation = recommend_product(
                {
                    "kind": "cover",
                    "outputs": ["png"],
                    "topic": "cycle source",
                    "readiness": {"node": True, "baoyu_core": True, "chromium": False},
                },
                catalog_root=root,
            )

        self.assertEqual(recommendation.status, "FAIL")
        self.assertIsNone(recommendation.product_id)
        self.assertIn("chromium", recommendation.missing_prerequisites)

    def test_catalog_requires_pptx_core_for_ppt_master_products(self) -> None:
        products = json.loads(
            (SKILL_ROOT / "catalog" / "products.json").read_text(encoding="utf-8")
        )
        product = next(item for item in products if item["id"] == "native-editable-deck")
        product["required_prerequisites"].remove("pptx_core")

        with self.assertRaisesRegex(CatalogError, "ppt-master requires pptx_core"):
            validate_products(products)

    def test_catalog_rejects_baoyu_core_without_a_baoyu_engine(self) -> None:
        products = json.loads(
            (SKILL_ROOT / "catalog" / "products.json").read_text(encoding="utf-8")
        )
        product = next(item for item in products if item["id"] == "html-presenter")
        product["required_prerequisites"].append("baoyu_core")

        with self.assertRaisesRegex(CatalogError, "baoyu_core requires baoyu"):
            validate_products(products)


class MultilingualRoutingTests(unittest.TestCase):
    def test_chinese_investor_brief_uses_catalog_signals(self) -> None:
        request = {
            "kind": "presentation",
            "outputs": ["pptx"],
            "topic": "人工智能产品战略",
            "audience": "投资者",
            "purpose": "融资路演",
            "tone": "专业",
            "channel": "会议",
            "density": "中等",
            "readiness": {"python": True, "node": True, "pptx_core": True},
        }

        self.assertTrue(_tokens(request["topic"]))

        recommendation = recommend_product(request)

        self.assertEqual(recommendation.product_id, "executive-deck")
        self.assertEqual(recommendation.style["selected"], "executive-minimal")

    def test_tokens_are_unicode_aware_and_immutable(self) -> None:
        tokens = _tokens("投资者路演：人工智能战略")

        self.assertIsInstance(tokens, frozenset)
        self.assertIn("投资者", tokens)
        self.assertIn("investors", tokens)

    def test_unmapped_han_span_emits_stable_unigrams_and_overlapping_bigrams(self) -> None:
        tokens = _tokens("量子计算")

        self.assertTrue(
            {"量", "子", "计", "算", "量子", "子计", "计算"}.issubset(tokens)
        )

    def test_han_span_includes_extension_plane_characters_and_cross_plane_bigrams(self) -> None:
        han_span = "\U00020000量"
        tokens = _tokens(han_span)

        self.assertIn(han_span, tokens)
        self.assertTrue({"\U00020000", "量"}.issubset(tokens))
        self.assertIn("\U00020000量", tokens)

    def test_reordered_catalog_uses_related_chinese_signal_not_item_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog"
            catalog.mkdir()
            products = json.loads(
                (SKILL_ROOT / "catalog" / "products.json").read_text(encoding="utf-8")
            )
            styles = (SKILL_ROOT / "catalog" / "styles.json").read_text(encoding="utf-8")
            native = next(product for product in products if product["id"] == "native-editable-deck")
            executive = next(product for product in products if product["id"] == "executive-deck")
            native["intended_uses"] = ["市场"]
            executive["intended_uses"] = ["量子"]
            request = {
                "kind": "presentation",
                "outputs": ["pptx"],
                "topic": "量子计算",
                "readiness": {"python": True, "node": True, "pptx_core": True},
            }

            for ordered_products in (products, list(reversed(products))):
                (catalog / "products.json").write_text(
                    json.dumps(ordered_products, ensure_ascii=False), encoding="utf-8"
                )
                (catalog / "styles.json").write_text(styles, encoding="utf-8")

                recommendation = recommend_product(request, catalog_root=root)

                self.assertEqual(recommendation.product_id, "executive-deck")

    def test_tone_can_change_inferred_style(self) -> None:
        neutral = recommend_product(
            {"kind": "presentation", "outputs": ["pptx"]}
        )
        confident = recommend_product(
            {
                "kind": "presentation",
                "outputs": ["pptx"],
                "tone": "confident",
            }
        )

        self.assertEqual(neutral.style["selected"], "swiss-editorial")
        self.assertEqual(confident.style["selected"], "bold-promotional")
        self.assertIn("tone", confident.style["score_breakdown"])

    def test_normalized_request_preserves_raw_text_and_shared_fields(self) -> None:
        request = normalize_request(
            {
                "topic": "AI 产品战略",
                "aspect_ratio": "16:9",
                "presenter": True,
                "single_file": True,
                "deadline": "2026-08-31",
                "brief_completeness": "Complete",
            }
        )

        self.assertEqual(request.raw_text, "AI 产品战略")
        self.assertEqual(request.topic, "ai 产品战略")
        self.assertEqual(request.aspect_ratio, "16:9")
        self.assertTrue(request.presenter)
        self.assertTrue(request.single_file)
        self.assertEqual(request.deadline, "2026-08-31")
        self.assertEqual(request.brief_completeness, "complete")

    def test_hard_constraints_consider_aspect_ratio_presenter_and_single_file(self) -> None:
        unsupported_ratio = recommend_product(
            {
                "kind": "presentation",
                "outputs": ["pdf"],
                "aspect_ratio": "4:3",
                "presenter": True,
                "single_file": True,
            }
        )
        unsupported_presenter_delivery = recommend_product(
            {
                "kind": "presentation",
                "outputs": ["pptx"],
                "presenter": True,
                "single_file": True,
            }
        )

        self.assertEqual(unsupported_ratio.status, "FAIL")
        self.assertIn("aspect_ratio", unsupported_ratio.conflicts[0])
        self.assertEqual(unsupported_presenter_delivery.status, "FAIL")
        self.assertIn("presenter", unsupported_presenter_delivery.conflicts[0])

    def test_selected_product_conflicts_for_shared_delivery_constraints(self) -> None:
        cases = (
            ({"aspect_ratio": "1:1"}, "aspect_ratio: 1:1"),
            ({"presenter": True}, "presenter: selected product does not support presenter mode"),
            ({"single_file": True}, "single_file: selected product does not support single-file delivery"),
        )
        for extra, conflict in cases:
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(ValueError, conflict):
                    route_request(
                        {
                            "kind": "presentation",
                            "outputs": ["pptx"],
                            "product": "native-editable-deck",
                            **extra,
                        }
                    )

    def test_selected_html_presenter_accepts_compatible_delivery_constraints(self) -> None:
        plan = route_request(
            {
                "kind": "presentation",
                "outputs": ["html", "pdf"],
                "product": "html-presenter",
                "aspect_ratio": "16:9",
                "presenter": True,
                "single_file": True,
            }
        )

        self.assertEqual(plan.engines, ("guizang", "frontend-slides"))

    def test_retrieval_request_compatibility_adapter_delegates_to_normalizer(self) -> None:
        raw = {"kind": "Pitch Deck", "topic": "AI Strategy", "outputs": ["PPT"]}

        compatibility_request = retrieval.RetrievalRequest.from_dict(raw)

        self.assertIs(retrieval.RetrievalRequest, Request)
        self.assertEqual(compatibility_request, normalize_request(raw))

    def test_productless_pdf_request_routes_to_frontend_slides(self) -> None:
        plan = route_request({"kind": "presentation", "outputs": ["pdf"]})

        self.assertEqual(plan.engines, ("frontend-slides",))
        self.assertEqual(plan.capabilities["frontend-slides"], ("html-slides", "html-pdf"))

    def test_unknown_catalog_style_conflicts_unless_freeform_is_explicit(self) -> None:
        request = {
            "kind": "presentation",
            "outputs": ["pptx"],
            "style": "custom-brand-style",
        }

        with self.assertRaisesRegex(ValueError, "Unknown catalog style: custom-brand-style"):
            recommend_product(request)
        with self.assertRaisesRegex(ValueError, "Unknown catalog style: custom-brand-style"):
            route_request(request)

        recommendation = recommend_product({**request, "style_source": "freeform"})
        plan = route_request({**request, "style_source": "freeform"})
        self.assertEqual(recommendation.style["selected"], "custom-brand-style")
        self.assertIn("ppt-master", plan.engines)


if __name__ == "__main__":
    unittest.main()
