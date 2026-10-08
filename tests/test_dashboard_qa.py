"""Smoke and edge-case tests for every dashboard page, using Streamlit's AppTest.

Each page must render against the real database without an exception, and the two
text-input pages must survive empty, huge, hostile and meaningless input. This catches the
failures a visitor would hit that unit tests of helper functions do not."""

import os

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

DASH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard")

PAGES = [
    ("overview", "render_overview"), ("program_explorer", "render_program_explorer"), ("compare", "render_compare"),
    ("heatmap", "render_heatmap"), ("trends", "render_trends"), ("clusters", "render_clusters"),
    ("course_finder", "render_course_finder"), ("match_job", "render_match_job"),
    ("profile", "render_profile_builder"), ("methodology", "render_methodology"),
]


def _page(module, func):
    code = f"import sys\nsys.path.insert(0, {DASH!r})\nfrom sections.{module} import {func}\n{func}()\n"
    return AppTest.from_string(code, default_timeout=90)


@pytest.mark.parametrize("module,func", PAGES)
def test_page_renders_without_exception(module, func):
    at = _page(module, func).run()
    assert not at.exception, [e.value for e in at.exception]


EDGE_INPUTS = {
    "empty": "",
    "whitespace": "   \n\t  ",
    "no_known_skills": "Lorem ipsum dolor sit amet. Banana smoothie recipes and gardening tips.",
    "huge": "We need Python, SQL, Docker and Kubernetes experience. " * 4000,
    "html_and_script": "<script>alert(1)</script><b>Python</b> & SQL ' \" ; DROP TABLE postings;--",
    "unicode": "Ingénieur données — Python, SQL \U0001F680 中文 مرحبا",
}


@pytest.mark.parametrize("name", list(EDGE_INPUTS))
def test_match_job_survives_edge_inputs(name):
    at = _page("match_job", "render_match_job").run()
    text_areas = {t.label: t for t in at.text_area}
    text_areas["The job posting"].set_value(EDGE_INPUTS[name])
    text_areas["Your skills"].set_value(EDGE_INPUTS[name])
    at.button[-1].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("name", list(EDGE_INPUTS))
def test_profile_builder_survives_edge_inputs(name):
    at = _page("profile", "render_profile_builder").run()
    at.text_area[0].set_value(EDGE_INPUTS[name])
    at.button[-1].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_home_signal_is_drawn_from_the_database():
    at = _page("overview", "render_overview").run()
    html = " ".join(m.value for m in at.markdown)
    assert "A Real Signal From The Data" in html
    assert "point gap" in html and "Curriculum" in html and "Job market" in html
