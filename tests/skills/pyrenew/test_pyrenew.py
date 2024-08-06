from .pyrenew_skills import *


def test_imports():
    assert build_renewal_model


def test_skill_tree():
    assert len(list(build_renewal_model.nodes)) == 6
    assert len(list(build_renewal_model.all_required_imports)) == 10
    assert len(list(build_renewal_model.head.inputs)) == 6
    assert len(list(build_renewal_model.head.variables)) == 2


def test_nodes_by_depth():
    nodes_by_depth = build_renewal_model.nodes_by_depth()

    assert len(nodes_by_depth) == 3
    assert [(depth, len(nodes)) for (depth, nodes) in nodes_by_depth] == [(1, 1), (2, 5), (3, 1)]
    assert nodes_by_depth[0][1][0].skill.display_name == "Define a RtInfections Renewal Model"
    assert nodes_by_depth[2][1][0].skill.display_name == "New deterministic generation interval"


def test_compile():
    compiled_text, variables, inputs = build_renewal_model.compile()
    # assert compiled_text == "foo"


def test_render():
    rendered_source = build_renewal_model.render()
    # print(f"Rendered: ============\n{rendered_source}\n========================")
    # assert rendered_source == False
