import typing
from ..model import Skill, TemplateVariable, SkillInputOutput
import uuid

get_local_vars = Skill(
    id=uuid.uuid4(),
    language="python3",
    inputs=[],
    outputs=[
        SkillInputOutput(
            type=list[typing.Any],
            skill_varname="local_vars",
            display_name="local_vars",
            description="Dictionary of variables in the local scope.",
            skill_varname="local_vars",
        ),
    ],
    source="{{ local_vars }} = dict(locals())",
    display_name="get_local_vars",
    description="Returns the variables in the local scope",
    required_imports=[],
    variables=[],
)
