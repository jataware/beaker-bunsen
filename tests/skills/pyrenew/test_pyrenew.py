from .pyrenew_skills import *


def test_imports():
    assert build_renewal_model


def test_skill_tree():
    assert len(list(build_renewal_model.nodes)) == 6
    assert len(list(build_renewal_model.all_required_imports)) == 13
    assert len(list(build_renewal_model.head.inputs)) == 6
    assert len(list(build_renewal_model.head.variables)) == 2


def test_nodes_by_depth():
    nodes_by_depth = build_renewal_model.nodes_by_depth()

    assert len(nodes_by_depth) == 3
    assert [(depth, len(nodes)) for (depth, nodes) in nodes_by_depth] == [(1, 1), (2, 5), (3, 1)]
    assert nodes_by_depth[0][1][0].skill.display_name == "Define a RtInfections Renewal Model"
    assert nodes_by_depth[2][1][0].skill.display_name == "New deterministic generation interval"


def test_compile():
    variables, variable_values, inputs, compiled_text = build_renewal_model.compile()
    assert isinstance(variables, list)
    assert isinstance(variable_values, dict)
    assert isinstance(inputs, list)
    assert isinstance(compiled_text, str)


def test_render():
    rendered_source = build_renewal_model.render()
    assert isinstance(rendered_source, str)
    assert 'base_rv=SimpleRandomWalkProcess' in rendered_source
    assert 'from pyrenew.model import RtInfectionsRenewalModel' in rendered_source
    assert 'InitializeInfectionsZeroPad(pmf_array.size),' in rendered_source
