"""Tests for LandscapeBootstrapper and InteractiveBootstrapSession (C299-C300).

Test structure (Option B — guided extraction):
    TestBootstrapValidationError    (4)  — error class attributes
    TestBootstrapEdgeSpec           (4)  — dataclass fields
    TestBootstrapSchema             (4)  — dataclass fields + warnings
    TestBootstrapResult             (3)  — dataclass fields
    TestNormalise                   (5)  — _normalise helper
    TestHasPath                     (6)  — _has_path BFS helper
    TestSafeFloat                   (4)  — _safe_float helper
    TestLandscapeBootstrapperInit   (5)  — constructor validation
    TestLandscapeBootstrapperParse  (12) — _validate_and_parse internals
    TestLandscapeBootstrapperBuild  (8)  — _build_landscape → Landscape
    TestLandscapeBootstrapperCall   (6)  — bootstrap() with fake call_fn
    TestInteractiveSessionChunks    (8)  — add_chunk, chunk_count, is_final
    TestInteractiveSessionFinalize  (7)  — finalize() behaviour
    TestInteractiveSessionErrors    (5)  — error paths
"""

from __future__ import annotations

import json
from typing import List

import pytest

from e0_controller.landscape_bootstrapper import (
    BootstrapEdgeSpec,
    BootstrapResult,
    BootstrapSchema,
    BootstrapValidationError,
    InteractiveBootstrapSession,
    LandscapeBootstrapper,
    _has_path,
    _normalise,
    _safe_float,
)
from e0_controller.landscape import Landscape
from e0_controller.llm_adapter import LLMConfig


# ── Fake LLM call_fn helpers ──────────────────────────────────────────────────

def _make_call_fn(response: str):
    """Return a call_fn that always returns the given string."""
    def _fn(system: str, user: str, config: LLMConfig) -> str:
        return response
    return _fn


def _valid_json(**extra) -> str:
    """Minimal valid JSON response from the LLM."""
    base = {
        "domain_summary": "A test domain",
        "edges": [
            {"source": "START", "target": "MIDDLE", "delta": 0.5, "resistance": 0.8, "label": "step 1"},
            {"source": "MIDDLE", "target": "GOAL",  "delta": 0.4, "resistance": 0.6, "label": "step 2"},
        ],
    }
    base.update(extra)
    return json.dumps(base)


def _make_bootstrapper(
    response: str = "",
    categories: List[str] = None,
    **kwargs,
) -> LandscapeBootstrapper:
    return LandscapeBootstrapper(
        categories=categories or ["decision point"],
        call_fn=_make_call_fn(response or _valid_json()),
        config=LLMConfig(model="test"),
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BootstrapValidationError
# ═══════════════════════════════════════════════════════════════════════════════

class TestBootstrapValidationError:
    def test_message(self):
        err = BootstrapValidationError("bad", errors=["e1"])
        assert "bad" in str(err)

    def test_errors_list(self):
        err = BootstrapValidationError("x", errors=["a", "b"])
        assert err.errors == ["a", "b"]

    def test_raw_default_empty(self):
        err = BootstrapValidationError("x", errors=[])
        assert err.raw == ""

    def test_raw_stored(self):
        err = BootstrapValidationError("x", errors=[], raw='{"broken')
        assert '{"broken' in err.raw


# ═══════════════════════════════════════════════════════════════════════════════
# BootstrapEdgeSpec
# ═══════════════════════════════════════════════════════════════════════════════

class TestBootstrapEdgeSpec:
    def test_fields_stored(self):
        e = BootstrapEdgeSpec("A", "B", 0.5, 1.0, "lbl")
        assert e.source == "A"
        assert e.target == "B"
        assert e.delta == 0.5
        assert e.resistance == 1.0
        assert e.label == "lbl"

    def test_label_default_empty(self):
        e = BootstrapEdgeSpec("A", "B", 0.3, 0.7)
        assert e.label == ""

    def test_delta_zero(self):
        e = BootstrapEdgeSpec("A", "B", 0.0, 0.0)
        assert e.delta == 0.0

    def test_equality(self):
        a = BootstrapEdgeSpec("A", "B", 0.5, 1.0, "x")
        b = BootstrapEdgeSpec("A", "B", 0.5, 1.0, "x")
        assert a == b


# ═══════════════════════════════════════════════════════════════════════════════
# BootstrapSchema
# ═══════════════════════════════════════════════════════════════════════════════

class TestBootstrapSchema:
    def _make(self, **kw):
        defaults = dict(
            states=["A", "B"],
            edges=[BootstrapEdgeSpec("A", "B", 0.5, 1.0)],
            start="A",
            goal="B",
        )
        defaults.update(kw)
        return BootstrapSchema(**defaults)

    def test_basic_fields(self):
        s = self._make()
        assert s.states == ["A", "B"]
        assert s.start == "A"
        assert s.goal == "B"

    def test_domain_summary_default(self):
        s = self._make()
        assert s.domain_summary == ""

    def test_skipped_edges_default_empty(self):
        s = self._make()
        assert s.skipped_edges == []

    def test_warnings_default_empty(self):
        s = self._make()
        assert s.warnings == []


# ═══════════════════════════════════════════════════════════════════════════════
# BootstrapResult
# ═══════════════════════════════════════════════════════════════════════════════

class TestBootstrapResult:
    def _make(self):
        schema = BootstrapSchema(
            states=["A", "B"],
            edges=[BootstrapEdgeSpec("A", "B", 0.5, 1.0)],
            start="A",
            goal="B",
        )
        return BootstrapResult(landscape=Landscape(), schema=schema)

    def test_landscape_stored(self):
        r = self._make()
        assert isinstance(r.landscape, Landscape)

    def test_raw_response_default_empty(self):
        r = self._make()
        assert r.raw_response == ""

    def test_llm_tokens_default_zero(self):
        r = self._make()
        assert r.llm_tokens == 0


# ═══════════════════════════════════════════════════════════════════════════════
# _normalise helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalise:
    def test_upper(self):
        assert _normalise("hello") == "HELLO"

    def test_spaces_to_underscore(self):
        assert _normalise("hello world") == "HELLO_WORLD"

    def test_hyphen_to_underscore(self):
        assert _normalise("hello-world") == "HELLO_WORLD"

    def test_strips_whitespace(self):
        assert _normalise("  hello  ") == "HELLO"

    def test_already_normalised(self):
        assert _normalise("INTEL_GAP") == "INTEL_GAP"


# ═══════════════════════════════════════════════════════════════════════════════
# _has_path helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestHasPath:
    def _edges(self, pairs):
        return [BootstrapEdgeSpec(s, t, 0.5, 1.0) for s, t in pairs]

    def test_direct_edge(self):
        assert _has_path(self._edges([("A", "B")]), "A", "B")

    def test_indirect_path(self):
        assert _has_path(self._edges([("A", "B"), ("B", "C")]), "A", "C")

    def test_no_path(self):
        assert not _has_path(self._edges([("A", "B")]), "A", "C")

    def test_same_start_goal(self):
        assert _has_path(self._edges([("A", "B")]), "A", "A")

    def test_empty_edges(self):
        assert not _has_path([], "A", "B")

    def test_longer_chain(self):
        edges = self._edges([("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")])
        assert _has_path(edges, "A", "E")


# ═══════════════════════════════════════════════════════════════════════════════
# _safe_float helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestSafeFloat:
    def test_valid_float(self):
        assert _safe_float(0.7, 0.5) == 0.7

    def test_none_returns_default(self):
        assert _safe_float(None, 0.5) == 0.5

    def test_string_invalid_returns_default(self):
        assert _safe_float("bad", 0.5) == 0.5

    def test_string_valid(self):
        assert _safe_float("0.3", 0.5) == pytest.approx(0.3)


# ═══════════════════════════════════════════════════════════════════════════════
# LandscapeBootstrapper — init validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestLandscapeBootstrapperInit:
    def test_empty_categories_raises(self):
        with pytest.raises(ValueError, match="categories must not be empty"):
            LandscapeBootstrapper(categories=[])

    def test_valid_init(self):
        bs = LandscapeBootstrapper(categories=["decision point"])
        assert bs is not None

    def test_default_config(self):
        bs = LandscapeBootstrapper(categories=["x"])
        assert bs._config is not None

    def test_custom_max_states(self):
        bs = LandscapeBootstrapper(categories=["x"], max_states=5)
        assert bs._max_states == 5

    def test_custom_defaults(self):
        bs = LandscapeBootstrapper(
            categories=["x"], default_delta=0.3, default_resistance=0.7
        )
        assert bs._default_delta == 0.3
        assert bs._default_resistance == 0.7


# ═══════════════════════════════════════════════════════════════════════════════
# LandscapeBootstrapper — _validate_and_parse
# ═══════════════════════════════════════════════════════════════════════════════

class TestLandscapeBootstrapperParse:
    def _bs(self, **kw):
        return LandscapeBootstrapper(
            categories=["decision point"],
            config=LLMConfig(model="test"),
            call_fn=_make_call_fn(""),
            **kw,
        )

    def test_invalid_json_raises(self):
        bs = self._bs()
        with pytest.raises(BootstrapValidationError, match="invalid JSON"):
            bs._validate_and_parse("{broken", "START", "GOAL")

    def test_missing_edges_key_raises(self):
        bs = self._bs()
        raw = json.dumps({"domain_summary": "x"})
        with pytest.raises(BootstrapValidationError, match="missing 'edges'"):
            bs._validate_and_parse(raw, "START", "GOAL")

    def test_non_list_edges_raises(self):
        bs = self._bs()
        raw = json.dumps({"edges": "not a list"})
        with pytest.raises(BootstrapValidationError):
            bs._validate_and_parse(raw, "START", "GOAL")

    def test_all_edges_invalid_raises(self):
        bs = self._bs()
        raw = json.dumps({"edges": [{"source": "", "target": "B"}]})
        with pytest.raises(BootstrapValidationError, match="No valid edges"):
            bs._validate_and_parse(raw, "START", "GOAL")

    def test_valid_edges_parsed(self):
        bs = self._bs()
        schema = bs._validate_and_parse(_valid_json(), "start", "goal")
        assert len(schema.edges) == 2

    def test_state_names_normalised(self):
        bs = self._bs()
        raw = json.dumps({
            "edges": [{"source": "start", "target": "goal", "delta": 0.5, "resistance": 1.0}]
        })
        schema = bs._validate_and_parse(raw, "start", "goal")
        assert schema.edges[0].source == "START"
        assert schema.edges[0].target == "GOAL"

    def test_delta_clamped_above(self):
        bs = self._bs()
        raw = json.dumps({
            "edges": [{"source": "A", "target": "B", "delta": 5.0, "resistance": 1.0}]
        })
        schema = bs._validate_and_parse(raw, "A", "B")
        assert schema.edges[0].delta == 1.0

    def test_resistance_clamped_above(self):
        bs = self._bs()
        raw = json.dumps({
            "edges": [{"source": "A", "target": "B", "delta": 0.5, "resistance": 99.0}]
        })
        schema = bs._validate_and_parse(raw, "A", "B")
        assert schema.edges[0].resistance == 2.0

    def test_self_loop_skipped(self):
        bs = self._bs()
        raw = json.dumps({
            "edges": [
                {"source": "A", "target": "A", "delta": 0.5, "resistance": 1.0},
                {"source": "A", "target": "B", "delta": 0.5, "resistance": 1.0},
            ]
        })
        schema = bs._validate_and_parse(raw, "A", "B")
        assert len(schema.edges) == 1
        assert len(schema.skipped_edges) == 1

    def test_missing_start_adds_isolated_state(self):
        bs = self._bs()
        raw = json.dumps({
            "edges": [{"source": "A", "target": "B", "delta": 0.5, "resistance": 1.0}]
        })
        schema = bs._validate_and_parse(raw, "MISSING_START", "B")
        assert "MISSING_START" in schema.states
        assert any("absent" in w for w in schema.warnings)

    def test_no_path_adds_warning(self):
        bs = self._bs()
        raw = json.dumps({
            "edges": [{"source": "A", "target": "B", "delta": 0.5, "resistance": 1.0}]
        })
        schema = bs._validate_and_parse(raw, "A", "C")
        assert any("No path" in w for w in schema.warnings)

    def test_domain_summary_stored(self):
        bs = self._bs()
        raw = _valid_json()
        schema = bs._validate_and_parse(raw, "START", "GOAL")
        assert schema.domain_summary == "A test domain"


# ═══════════════════════════════════════════════════════════════════════════════
# LandscapeBootstrapper — _build_landscape
# ═══════════════════════════════════════════════════════════════════════════════

class TestLandscapeBootstrapperBuild:
    def _schema(self, edges=None, states=None):
        edges = edges or [BootstrapEdgeSpec("A", "B", 0.5, 1.0)]
        states = states or ["A", "B"]
        return BootstrapSchema(
            states=states,
            edges=edges,
            start="A",
            goal="B",
        )

    def _bs(self):
        return LandscapeBootstrapper(
            categories=["x"], config=LLMConfig(model="test"),
            call_fn=_make_call_fn("")
        )

    def test_landscape_type(self):
        ls = self._bs()._build_landscape(self._schema())
        assert isinstance(ls, Landscape)

    def test_states_present(self):
        ls = self._bs()._build_landscape(self._schema())
        assert "A" in ls.states
        assert "B" in ls.states

    def test_edge_present(self):
        ls = self._bs()._build_landscape(self._schema())
        from e0_controller.primitives import Edge
        assert Edge("A", "B") in ls._delta

    def test_delta_correct(self):
        ls = self._bs()._build_landscape(self._schema())
        from e0_controller.primitives import Edge
        assert ls._delta[Edge("A", "B")] == pytest.approx(0.5)

    def test_resistance_correct(self):
        ls = self._bs()._build_landscape(self._schema())
        from e0_controller.primitives import Edge
        assert ls._R0[Edge("A", "B")] == pytest.approx(1.0)

    def test_isolated_state_present(self):
        schema = self._schema(
            edges=[BootstrapEdgeSpec("A", "B", 0.5, 1.0)],
            states=["A", "B", "ISOLATED"],
        )
        ls = self._bs()._build_landscape(schema)
        assert "ISOLATED" in ls.states

    def test_multiple_edges(self):
        edges = [
            BootstrapEdgeSpec("A", "B", 0.5, 1.0),
            BootstrapEdgeSpec("B", "C", 0.3, 0.8),
        ]
        schema = self._schema(edges=edges, states=["A", "B", "C"])
        ls = self._bs()._build_landscape(schema)
        assert len(ls.edges) == 2

    def test_empty_historization(self):
        ls = self._bs()._build_landscape(self._schema())
        # No transitions yet — historization should be clean
        for edge in ls.edges:
            assert ls.historization.trace_load(edge) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# LandscapeBootstrapper — bootstrap() integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestLandscapeBootstrapperCall:
    def test_empty_chunks_raises(self):
        bs = _make_bootstrapper()
        with pytest.raises(ValueError, match="chunks must not be empty"):
            bs.bootstrap([], "A", "B")

    def test_returns_bootstrap_result(self):
        bs = _make_bootstrapper()
        result = bs.bootstrap(["some domain text"], "START", "GOAL")
        assert isinstance(result, BootstrapResult)

    def test_result_landscape_is_landscape(self):
        bs = _make_bootstrapper()
        result = bs.bootstrap(["some domain text"], "START", "GOAL")
        assert isinstance(result.landscape, Landscape)

    def test_result_has_states(self):
        bs = _make_bootstrapper()
        result = bs.bootstrap(["text"], "START", "GOAL")
        assert len(result.landscape.states) > 0

    def test_raw_response_stored(self):
        raw = _valid_json()
        bs = _make_bootstrapper(response=raw)
        result = bs.bootstrap(["text"], "START", "GOAL")
        assert result.raw_response == raw

    def test_invalid_llm_response_raises(self):
        bs = _make_bootstrapper(response="{broken json")
        with pytest.raises(BootstrapValidationError):
            bs.bootstrap(["text"], "A", "B")


# ═══════════════════════════════════════════════════════════════════════════════
# InteractiveBootstrapSession — chunk management
# ═══════════════════════════════════════════════════════════════════════════════

class TestInteractiveSessionChunks:
    def _session(self, response: str = ""):
        return InteractiveBootstrapSession(
            categories=["decision point"],
            config=LLMConfig(model="test"),
            call_fn=_make_call_fn(response or _valid_json()),
        )

    def test_initial_chunk_count_zero(self):
        s = self._session()
        assert s.chunk_count == 0

    def test_add_chunk_increments_count(self):
        s = self._session()
        s.add_chunk("text 1")
        assert s.chunk_count == 1

    def test_add_multiple_chunks(self):
        s = self._session()
        s.add_chunk("a")
        s.add_chunk("b")
        s.add_chunk("c")
        assert s.chunk_count == 3

    def test_empty_string_ignored(self):
        s = self._session()
        s.add_chunk("")
        assert s.chunk_count == 0

    def test_whitespace_only_ignored(self):
        s = self._session()
        s.add_chunk("   ")
        assert s.chunk_count == 0

    def test_chunks_property_returns_copy(self):
        s = self._session()
        s.add_chunk("x")
        chunks = s.chunks
        chunks.append("y")
        assert s.chunk_count == 1  # original unmodified

    def test_is_final_initially_false(self):
        s = self._session()
        assert not s.is_final

    def test_result_initially_none(self):
        s = self._session()
        assert s.result is None


# ═══════════════════════════════════════════════════════════════════════════════
# InteractiveBootstrapSession — finalize()
# ═══════════════════════════════════════════════════════════════════════════════

class TestInteractiveSessionFinalize:
    def _session(self, response: str = ""):
        return InteractiveBootstrapSession(
            categories=["decision point"],
            config=LLMConfig(model="test"),
            call_fn=_make_call_fn(response or _valid_json()),
        )

    def test_finalize_returns_result(self):
        s = self._session()
        s.add_chunk("some context")
        result = s.finalize("START", "GOAL")
        assert isinstance(result, BootstrapResult)

    def test_is_final_after_finalize(self):
        s = self._session()
        s.add_chunk("text")
        s.finalize("START", "GOAL")
        assert s.is_final

    def test_result_accessible_after_finalize(self):
        s = self._session()
        s.add_chunk("text")
        s.finalize("START", "GOAL")
        assert s.result is not None

    def test_landscape_usable_after_finalize(self):
        s = self._session()
        s.add_chunk("text")
        result = s.finalize("START", "GOAL")
        assert isinstance(result.landscape, Landscape)

    def test_multiple_chunks_combined(self):
        # verify call_fn receives combined chunks in user message
        received = []
        def capturing_fn(system, user, config):
            received.append(user)
            return _valid_json()

        s = InteractiveBootstrapSession(
            categories=["decision point"],
            config=LLMConfig(model="test"),
            call_fn=capturing_fn,
        )
        s.add_chunk("chunk A")
        s.add_chunk("chunk B")
        s.finalize("START", "GOAL")
        assert len(received) == 1
        assert "chunk A" in received[0]
        assert "chunk B" in received[0]

    def test_schema_start_goal_normalised(self):
        s = self._session()
        s.add_chunk("text")
        result = s.finalize("my start", "my goal")
        assert result.schema.start == "MY_START"
        assert result.schema.goal == "MY_GOAL"

    def test_single_llm_call(self):
        call_count = [0]
        def counting_fn(system, user, config):
            call_count[0] += 1
            return _valid_json()

        s = InteractiveBootstrapSession(
            categories=["decision point"],
            config=LLMConfig(model="test"),
            call_fn=counting_fn,
        )
        s.add_chunk("a")
        s.add_chunk("b")
        s.finalize("S", "G")
        assert call_count[0] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# InteractiveBootstrapSession — error paths
# ═══════════════════════════════════════════════════════════════════════════════

class TestInteractiveSessionErrors:
    def _session(self):
        return InteractiveBootstrapSession(
            categories=["decision point"],
            config=LLMConfig(model="test"),
            call_fn=_make_call_fn(_valid_json()),
        )

    def test_add_chunk_after_finalize_raises(self):
        s = self._session()
        s.add_chunk("text")
        s.finalize("A", "B")
        with pytest.raises(RuntimeError, match="frozen"):
            s.add_chunk("late chunk")

    def test_finalize_twice_raises(self):
        s = self._session()
        s.add_chunk("text")
        s.finalize("A", "B")
        with pytest.raises(RuntimeError, match="already called"):
            s.finalize("A", "B")

    def test_finalize_without_chunks_raises(self):
        s = self._session()
        with pytest.raises(RuntimeError, match="No chunks"):
            s.finalize("A", "B")

    def test_invalid_llm_output_propagates(self):
        s = InteractiveBootstrapSession(
            categories=["x"],
            config=LLMConfig(model="test"),
            call_fn=_make_call_fn("{bad json"),
        )
        s.add_chunk("text")
        with pytest.raises(BootstrapValidationError):
            s.finalize("A", "B")

    def test_empty_categories_raises_on_init(self):
        with pytest.raises(ValueError, match="categories must not be empty"):
            InteractiveBootstrapSession(categories=[])
