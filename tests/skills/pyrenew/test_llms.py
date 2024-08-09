import inspect
import json
import os
import pytest

from beaker_bunsen.skills.model import Skill, SkillTree, AgentResponse
from . import pyrenew_skills

import openai


def setup_module(module):
    """Skip all tests in this file if OPEN_API_KEY not set."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("Skipping as OPENAI_API_KEY environment variable not set")


@pytest.fixture
def skill_list():
    all_skills = [skill for _name, skill in inspect.getmembers(pyrenew_skills, lambda obj: isinstance(obj, Skill))]
    return all_skills


@pytest.fixture
def skill_index(skill_list):
    return {skill.id: skill for skill in skill_list}


@pytest.fixture
def system_message(skill_list):
    from beaker_bunsen.skills.skills.builtins import union_skill
    skill_list.extend([union_skill])
    skill_list_str = "\n\n".join(map(str, skill_list))
    return {
        "role": "system",
        "content": f"""
You are an agent that is helping a user by instantiating and executing "skills", where the skills provide pre-written,
templated code designed to solve known problems.

Here is a list of some available skills:
```
{skill_list_str}
```

When queried by the user, try to determine if any of the skills will help the user achieve the desired task or query.
If you do find an appropriate skill, return uid of the skill, along with a dictionary where the keys are the names of
template variable and the corresponding values are strings containing code that should replace those variables.
As the value is a code string, if value should be a string literal, be sure to properly encode and enclose the string
for the programming language so that it is interpreted correctly. Likewise, ensure that all variable names are not
encoded as strings (e.g. surrounded by quotes) but are returned as the raw variable name.

In addition to providing values for the variables, either collected from the prompt, context, or inferred, you may use
these sentinel literal values as either names or values in a variables_value response:
  "<!<ASK>>": Indicates that the system will ask the user to provide the value at a later point.
  "<!<UNKNOWN>>": Indicates that you do not have enough information to determine the proper value, or how it
    should be determined. If this is value is returned, the system will try to collect more information and try again to
    resolve the variable before first use, if possible.

Skills can be used individually, or skills can be combined into a SkillTree. A SkillTree will be combined and rendered
via a later step, and may be renderd, but please try to ensure that the SkillTree is defined properly.
A single Skill is essentially a SkillTree without any parents.

When creating a SkillTree, be sure to include all Skills that are required, but no more. If a variable already exists in
the environment that would satisfy the request and is the only choice, do not include any Skill that defines that
variable, just include the environment variable in the skill's variable values. If there is ambiguity, go ahead and ask.

SkillTree docs:
```text
{SkillTree.__doc__}
```

A SkillTree may or may not be broken up into multiple sub-trees which will be executed seperately, however you should
always return the full tree as the splitting and execution will happen in a later step.

Please respond with json in the following format:
```json-schema
{json.dumps(AgentResponse.model_json_schema(), indent=2)}
```
        """.strip(),
    }

def query(system_message, query, extra_system_messages=None):
    model = "gpt-4o"
    messages=[
        system_message,
    ]
    if extra_system_messages:
        if isinstance(extra_system_messages, list):
            messages.extend(extra_system_messages)
        else:
            messages.append(extra_system_messages)

    messages.append(
        {
            "role": "user",
            "content": str(query).strip(),
        }
    )

    llm_response = openai.chat.completions.create(
        model=model,
        messages=messages,
        response_format={
            "type": "json_object"
        }
    )
    llm_response_content = llm_response.choices[0].message.content.strip()
    return llm_response_content


def test_skill_not_found(system_message):
    llm_response = query(system_message, "Please create draw a picture of a rabbit.")
    response = json.loads(llm_response)
    result = AgentResponse(**response)
    assert result.item_type == "Error"
    assert isinstance(result.item.error, str)


def test_response_env_variables_and_output_names(system_message):
    llm_response = query(
        system_message,
        "Create a new I-Naught variable with a normal distribution 'LogNormal(5.0, 1). Name the new variable 'i_naught'.",
        extra_system_messages=[
            {
                "role": "system",
                "content": (
                    "The following variables are defined in the environment:\n"
                    "  `m`: <pyrenew.model.rtinfectionsrenewalmodel.RtInfectionsRenewalModel object at 0x7f1503ad4710>\n"
                    "  `pmf_data_array`: Array([0.8, 0.2, 1.1, 5.1, 1.0], dtype=float32)\n"
                )
            }
        ]
    )
    response = json.loads(llm_response)
    result = AgentResponse(**response)

    assert isinstance(response, dict)
    assert result.item_type == "Skill"
    assert result.item.skill_id == "1090bd2d14714a598f8062515479a51d"
    assert result.item.variable_values.get("I0_distribution", None) == "dist.LogNormal(5.0, 1)"
    assert result.item.variable_values.get("pmf_array", None) == "pmf_data_array"
    assert result.item.variable_values.get("I0", None) == "i_naught"
    assert len(result.item.parents) == 0


def test_skill_build_tree(system_message):
    message = """
Please create a new pyrenew model that I can use to determine rtinfections with a normal distribution of (5.1, 1) for I0
and pmf values of [0.9, 0.8, 0.5, 0.3, 0.2, 0.1].
    """.strip()
    llm_response = query(system_message, message)
    response = json.loads(llm_response)
    result = AgentResponse(**response)
    parent_ids = set(parent.skill_id for parent in result.item.parents)
    assert result.item_type == "Skill"
    assert result.item.skill_id == "4079c3d38fd5459f9538a82b73cc71f4"
    assert len(result.item.parents) >= 1  # At minimum 2 parents are required, but may be more
    assert parent_ids == {
        "df845515b86240b0b3e5153c8deca6e9",
        "f8a02af4ac514f629418089f9057c2ab",
        "20b0624245044e0bbc23ba8426bebbec",
        "f2f12e2bfe114b42a24eadb151f4022f",
        "1090bd2d14714a598f8062515479a51d",
        "f8a02af4ac514f629418089f9057c2ab",
    }


def test_build_skilltree_object(system_message, skill_index):
    message = """
Please create a new pyrenew model that I can use to determine rtinfections with a normal distribution of (5.1, 1) for I0
and pmf values of [0.9, 0.8, 0.5, 0.3, 0.2, 0.1].
    """.strip()
    llm_response = query(system_message, message)
    response = json.loads(llm_response)
    result = AgentResponse(**response)
    skill_tree = SkillTree.from_agent_response(result, skill_index)

    rendered_code = skill_tree.render()
    lines = rendered_code.splitlines()
    import_lines = [line for line in lines if (line.startswith('from ') or line.startswith('import '))]
    pmf_value_line = next((line for line in lines if 'pmf_array =' in line), None)

    assert isinstance(rendered_code, str)
    assert len(import_lines) == 13
    # Slightly awkward tests to get around potential whitespace differences without using regular expressions.
    assert "(5.1, 1)" in rendered_code
    assert 'jnp.array([0.9, 0.8, 0.5, 0.3, 0.2, 0.1])' in pmf_value_line
