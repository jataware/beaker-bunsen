from .pyrenew_skills import *


def test_imports():
    assert build_renewal_model


def test_skill_tree():
    assert len(list(build_renewal_model.nodes)) == 6
    assert len(list(build_renewal_model.all_required_imports)) == 10
    assert len(list(build_renewal_model.head.inputs)) == 6
    assert len(list(build_renewal_model.head.variables)) == 2
