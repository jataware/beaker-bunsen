
from beaker_bunsen.skills.model import Skill, TemplateVariable, SkillInputOutput


def test_basic_templating():
    test_skill = Skill(
        id="test-skill-1",
        display_name="template test 1",
        description="testing",
        required_imports=[],
        inputs=[],
        outputs=[],
        language="python3",
        variables=[
            TemplateVariable(
                id="test-templatevar-1",
                variable="location",
                display_name="location",
                description="Place to greet",
                type_str=str,
                default="world",
            )
        ],
        source="""
print("Hello {{ location }}")
""".strip()
    )
    rendered_source_default = test_skill.render()
    rendered_source_arg = test_skill.render(location="New York")

    assert rendered_source_default == 'print("Hello world")'
    assert rendered_source_arg == 'print("Hello New York")'


def test_input_templating():


    flag_map_var = TemplateVariable(
        display_name="Flag map",
        description="A mapping of flags by country",
        variable="flag_map",
        type_str="dict[str, str]",
    )

    flag_var = TemplateVariable(
        display_name="Country Flag",
        description="The flag associated with a country",
        variable="flag",
        type_str=str,
    )

    country_var = TemplateVariable(
                variable="country",
                display_name="country",
                description="name of country to check",
                type_str=str,
                default="france",
            )


    test_skill = Skill(
        id="test-skill-2",
        display_name="template test 2",
        description="testing",
        required_imports=[],
        language="python3",
        inputs=[
            SkillInputOutput(
                display_name="European Flags",
                description="A mapping of flags ",
                variable="flags",
                type_str="dict[str, str]",
                template_variable=flag_map_var,
            ),
        ],
        outputs=[
            SkillInputOutput(
                display_name="european_flag",
                description="flag of a country",
                type_str=str,
                variable="myflag",
                template_variable=flag_var,
           ),
        ],
        variables=[
            country_var
        ],
        source="""{{ flag }} = {{ flag_map }}["{{country}}"]""",
    )

    rendered_source_default = test_skill.render()
    rendered_source_arg = test_skill.render(country="germany")

    assert rendered_source_default == 'myflag = flags["france"]'
    assert rendered_source_arg == 'myflag = flags["germany"]'
    assert country_var.id is not None


def test_template_default_id():
    var = TemplateVariable(
        display_name="123",
        description="123",
        variable="foo",
        type_str="list[str]",
        default="hello world",
    )
    assert isinstance(var.id, str)
