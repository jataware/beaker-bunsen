import os
import pytest
import zipfile
from pathlib import Path

import pandas

from beaker_bunsen.skills.model import Skill, SkillTree, SkillTreeNode, SkillInputOutput, TemplateVariable

@pytest.fixture()
def skills():
    basic_table = SkillInputOutput(
        display_name="basic_table",
        description="Simple 3x3 Pandas dataframe of floats",
        type=pandas.DataFrame,
        # variable=TemplateVariable(
        #     id="test-var-1",
        #     display_name="test_table_var",
        #     variable="table1",
        #     description="Holds a reference to the basic table variable",
        #     type=pandas.DataFrame,
        # )
    )
    skill1 = Skill(
        id="test1",
        display_name="TableCreationSkill",
        description="Skill that creates a 3x3 Pandas dataframe of floats",
        required_imports=["pandas as pd", "numpy"],
        inputs=[],
        outputs=[
            basic_table
        ],
        language="python3",
        source="""{{ test_table_var }} = pd.DataFrame([[1.0, 2.0, 3.0], [2.1, 2.2, 2.3], [3.3, 4.4, 5.5]])""".strip(),
        variables=[],
    )

    skill2 = Skill(
        id="test2",
        display_name="TableSummarySkill",
        description="Summarizes a table",
        required_imports=["pandas as pd"],
        inputs=[basic_table],
        outputs=[],
        language="python3",
        source="""print({{ test_table_var }}.describe())""",
        variables=[]
    )
    return [skill1, skill2]


def test_node_creation(skills):
    node = SkillTreeNode(
        id="test-node1",
        parents=[],
        tree=None,
        skill=skills[0]
    )
    assert isinstance(node, SkillTreeNode)
    assert node.id == "test-node1"
    assert node.parents == []
    assert node.skill.id == "test1"


def test_basic_skilltree(skills):
    node1 = SkillTreeNode(
        id="test-node1",
        parents=[],
        # tree=None,
        skill=skills[0]
    )
    node2 = SkillTreeNode(
        id="test-node2",
        parents=[node1],
        # tree=None,
        skill=skills[1]
    )
    tree = SkillTree(
        display_name="test_basic_tree",
        description="Testing",
        head=node2,
    )
    assert tree
    assert list(tree.nodes) == [node2, node1]
    assert set(tree.all_required_imports) == set(["pandas as pd", "numpy"])
    assert tree.resolved == False
