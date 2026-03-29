from __future__ import annotations

import py_compile

from prosperity.compilation.spec_to_strategy import compile_strategy_module, render_strategy_module


def test_render_strategy_module_embeds_json_spec(sample_spec, tmp_path):
    template_path = tmp_path / "template.py.j2"
    template_path.write_text("SPEC = __SPEC_JSON__\n", encoding="utf-8")
    rendered = render_strategy_module(sample_spec, template_path)
    assert '"metadata"' in rendered


def test_compile_strategy_module_produces_valid_python(sample_spec, tmp_path):
    template_path = (
        tmp_path.parent
        / "src"
        / "prosperity"
        / "compilation"
        / "templates"
        / "strategy_module.py.j2"
    )
    if not template_path.exists():
        template_path = (
            sample_spec.__class__.__module__  # pragma: no cover
        )
    actual_template = (
        tmp_path.parent.parent
        / "src"
        / "prosperity"
        / "compilation"
        / "templates"
        / "strategy_module.py.j2"
    )
    if actual_template.exists():
        template_path = actual_template
    else:
        template_path = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "src"
            / "prosperity"
            / "compilation"
            / "templates"
            / "strategy_module.py.j2"
        )
    output_path = tmp_path / "compiled.py"
    compile_strategy_module(sample_spec, output_path, template_path)
    py_compile.compile(str(output_path), doraise=True)
