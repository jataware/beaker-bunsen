import typing
from ..model import Skill, TemplateVariable, SkillInputOutput

# get_local_vars_skill = Skill(
#     id="90cd9b51-6b37-4b0c-b52d-847cfd6940a6",
#     language="python3",
#     inputs=[],
#     outputs=[
#         SkillInputOutput(
#             type_str=list[typing.Any],
#             skill_varname="local_vars",
#             display_name="local_vars",
#             description="Dictionary of variables in the local scope.",
#             skill_varname="local_vars",
#         ),
#     ],
#     source="{{ local_vars }} = dict(locals())",
#     display_name="get_local_vars",
#     description="Returns the variables in the local scope",
#     required_imports=[],
#     variables=[],
# )

union_skill = Skill(
    id="5001a929-c602-43ea-9865-8f6750063eb1",
    display_name="union_skill",
    description="Synthetic skill which combines two parent skills without performing any other actions.",
    language="any",
    variables=[],
    inputs=[],
    outputs=[],
    source="",
    required_imports=[],
)
