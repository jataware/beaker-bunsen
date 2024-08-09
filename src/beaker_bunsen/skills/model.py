import itertools
import types
import typing
from collections import deque
from pydantic import BaseModel, Field, ConfigDict, UUID4
from types import GenericAlias
from typing_extensions import Self, TypeAliasType, assert_type
from uuid import uuid4

import jinja2


TemplateVarType = typing.TypeVar('TemplateVarType')

IDType: typing.TypeAlias = str
UUIDField: typing.TypeAlias = typing.Annotated[IDType, Field(default_factory=lambda: uuid4().hex)]

import typing
TemplateVariable_ASK = typing.Literal["<!<ASK>>"]
TemplateVariable_UNKNOWN = typing.Literal["<!<UNKNOWN>>"]

TemplateVariableSentinel: typing.TypeAlias = typing.Literal[
    TemplateVariable_ASK,
    TemplateVariable_UNKNOWN,
]
TemplateVariableName: typing.TypeAlias = TemplateVariableSentinel | str
TemplateVariableValue: typing.TypeAlias = TemplateVariableSentinel | typing.Any
TemplateVariableDict: typing.TypeAlias = dict[TemplateVariableName, TemplateVariableValue]

TemplateVariableSentinelValues: list[TemplateVariableSentinel] = typing.get_args(TemplateVariableSentinel)

class TemplateVariable(BaseModel):
    """
    A definition of a template variable to be used in skill templates.

    A template variable may be used in multiple templates or multiple times in a single template.
    The id and template_var must be unique across all template variables defined within a context.
    """
    id: UUIDField
    variable: TemplateVariableName
    display_name: str
    description: str
    type_str: str | type
    default: TemplateVarType | None = None # TODO: Figure out how well this (the typing) works and how to store arbitrary defaults a in sqlite db

    def model_post_init(self, __context: typing.Any) -> types.NoneType:
        if isinstance(self.type_str, type):
            self.type_str = str(self.type_str)
        return super().model_post_init(__context)

    def __str__(self) -> str:
        return "\n".join([
            f'TemplateVariable:',
            f'  template variable: `{self.variable}`',
            f'  uid: {self.id}',
            f'  display name: {self.display_name}',
            f'  description: {self.description}',
            f'  type: {self.type_str}',
            f'  default value: ```{self.default}```'
        ])


class SkillInputOutput(BaseModel):  # TODO: Better name?
    """
    Things that need to exist in the environment so that the skill can use it or that a skill produces.
    Can be used to create a tree allowing skills to be chained together.
    """
    instance_count: typing.ClassVar[dict[str, int]] = {}

    id: UUIDField
    display_name: str
    description: str
    type_str: str | type
    resolved: bool = False
    variable: str
    template_variable: TemplateVariable | None = None

    def model_post_init(self, __context: typing.Any) -> None:
        if not isinstance(self.type_str, str):
            self.type_str = str(self.type_str)
        if self.template_variable is None:
            # Build default template variable instance
            self.template_variable = TemplateVariable(
                variable=self.variable,
                type_str=self.type_str,
                display_name=self.display_name,
                description=self.description,
            )
        return super().model_post_init(__context)

    @property
    def varname(self):
        return self.template_variable.variable if self.template_variable else None

    def __str__(self) -> str:
        return "\n".join([
            f'InputOutputVariable:',
            f'  uid: {self.id}',
            f'  display name: {self.display_name}',
            f'  description: {self.description}',
            f'  type: {self.type_str}',
            f'  variable name in code: `{self.variable}`',
            f'  template variable: `{self.template_variable.variable}`'
        ])


class Skill(BaseModel):
    """
    Basic unit of "work" consisting of a templated portion of code that can be executed by Bunsen.
    The skill may be executed by itself or combined into a larger set of code by combining multiple Skills into one
    codeset.
    Skills import and output SkillInputOutput items, which are annotated references to variables that exist in the
    environment. As the inputs and outputs are the same type, skills can be chained such that the output of an earlier
    skill can be used by another skill, either as part of the same "plan" or as part of a subsequent interaction.
    """
    id: UUIDField
    display_name: str
    description: str
    required_imports: list[str]
    variables: list[TemplateVariable]
    source: str
    language: str  # type TBD
    inputs: list[SkillInputOutput]
    outputs: list[SkillInputOutput]
    # examples: list[{description, source, etc}] ?

    def resolve(self):
        # TODO: Fill this out
        return True

    def render(self, **kwarg):
        template = jinja2.Template(self.source)
        vars = kwarg
        for var in self.variables:
            if var.variable in vars:  # Passed in as an argument
                continue
            elif var.default != None:  # TODO: Do we need to pass in None? Should this be a singleton?
                vars[var.variable] = var.default
            else:
                raise
        for input in self.inputs:
            if input.display_name not in vars:
                vars[input.template_variable.variable] = input.variable
        for output in self.outputs:
            if output.display_name not in vars:
                vars[output.template_variable.variable] = output.variable
        return template.render(vars)

    def __str__(self) -> str:
        return "\n".join([
            f'Skill:',
            f'  uid: {self.id}',
            f'  display name: {self.display_name}',
            f'  description: {self.description}',
            f'  required imports:',
            *[f'    "{import_str}"' for import_str in self.required_imports],
            f'  variables:',
            *[f'    {line}' for variable in self.variables for line in str(variable).splitlines()],
            f'  inputs:',
            *[f'    {line}' for input in self.inputs for line in str(input).splitlines()],
            f'  outputs:',
            *[f'    {line}' for output in self.outputs for line in str(output).splitlines()],
            f'  language: {self.language}',
            f'  skill source code:\n    ```\n{self.source}\n    ```',
        ])

class SkillTree(BaseModel):
    r"""
    A collection of skills that work together and may becomes a new skill itself.
    This allows dynamic building of more complex skills, using skills already learned.

    This can be thought of as a non-inverted tree with the root (at the bottom) with requirements (parents) as leaf
    nodes above. Multiple nodes can reference the same parent.

        #  #
       / \/ \  - Shared parents
    #  # #  #
    \ /  \ /
     #    #     #
     \    |    /
      \   |   /
       \  |  /
        \ | /
        Root

    The root contains the code/skill that is the intended action where the parents are included to provide prerequisite
    actions such that the root skill can complete.
    A skill tree can be compiled to become a new single skill, or can be saved in tree form for (potentially) dynamic
    reuse.
    """
    id: UUIDField
    display_name: str
    description: str
    head: "SkillTreeNode"


    @classmethod
    def from_agent_response(cls: type[Self], agent_result: 'AgentResponse', skill_index: dict[str, Skill]):
        # head = parse_node_tree()
        def build_tree(skill_response: SkillResponse):
            return SkillTreeNode(
                skill=skill_index[skill_response.skill_id],
                parents=[build_tree(parent) for parent in skill_response.parents],
                variable_values=skill_response.variable_values,
            )
        head = build_tree(agent_result.item)
        return cls(
            display_name="Unsaved SkillTree 1",
            description="Dynamically generated SkillTree from a LLM Agent Response",
            head=head
        )

    @property
    def nodes(self) -> typing.Iterable["SkillTreeNode"]:
        """
        No duplicates
        """
        seen_nodes = set()
        search_nodes = deque([self.head])
        while search_nodes:
            try:
                node = search_nodes.popleft()
            except IndexError:
                # Nothing remains
                break
            # Ensure we skip nodes we've already seen
            if node.id in seen_nodes:
                continue
            seen_nodes.add(node.id)

            yield node
            search_nodes.extend(node.parents)

    def nodes_by_depth(self) -> list[tuple[int, list["SkillTreeNode"]]]:
        """
        Contains duplicates
        """
        current_depth = 1
        nodes_at_depth = [self.head]
        nodes_at_next_level = []
        output = []
        while nodes_at_depth:
            for node in nodes_at_depth:
                nodes_at_next_level.extend(node.parents)
            output.append([current_depth, nodes_at_depth])
            nodes_at_depth = nodes_at_next_level
            nodes_at_next_level = []
            current_depth += 1
        return output

    @property
    def all_required_imports(self) -> list[str]:
        requirements = set()
        for node in self.nodes:
            requirements.update(node.skill.required_imports)
        return list(requirements)

    @property
    def resolved(self) -> bool:
        return all(node.resolved for node in self.nodes)

    def resolve(self) -> bool:
        if self.resolved:
            return True

    def compile(self) -> tuple[list[TemplateVariable], TemplateVariableDict, list[SkillInputOutput], str]:
        variables = []
        variable_values = {}
        inputs = []
        source_parts = []
        source_parts.append("\n".join(sorted(self.all_required_imports)))

        seen_variables = set()
        seen_inputs = set()
        seen_nodes = set()

        for _, nodes in sorted(self.nodes_by_depth(), reverse=True, key=lambda obj: obj[0]):
            for node in nodes:
                if node.id in seen_nodes:
                    continue
                seen_nodes.add(node.id)

                new_variables = node.skill.variables
                # new_variable_values = node.variable_values
                if node.variable_values:
                    variable_values.update({
                        var_name: var_value
                        for var_name, var_value in node.variable_values.items()
                        if var_name not in variable_values
                    })
                variables.extend(variable for variable in new_variables if variable.id not in seen_variables)
                seen_variables.update(variable.id for variable in new_variables)
                new_inputs = node.skill.inputs
                inputs.extend(input for input in new_inputs if input.id not in seen_inputs)
                seen_inputs.update(input.id for input in new_inputs)
                source_parts.append(node.skill.source)

        return variables, variable_values, inputs, "\n\n".join(source_parts)


    def render(self, **kwargs):
        variables, variable_values, inputs, source = self.compile()
        outputs = self.head.skill.outputs

        template = jinja2.Template(source)
        # Ensure that we accept render method values over values extracted from the tree, if provided.
        variable_values.update(kwargs)

        for var in variables:
            if var.variable in variable_values:  # Passed in as an argument
                continue
            elif var.default != None:  # TODO: Do we need to pass in None? Should this be a singleton?
                variable_values[var.variable] = var.default
            else:
                raise
        for input in inputs:
            if input.template_variable.variable not in variable_values:
                variable_values[input.template_variable.variable] = input.variable
        for output in outputs:
            if output.template_variable.variable not in variable_values:
                variable_values[output.template_variable.variable] = output.variable
        return template.render(variable_values)


    def model_post_init(self, __context: typing.Any) -> None:
        return super().model_post_init(__context)


class BranchingSkillTree:
    """
    A "mega" tree that contains multiple paths/branches, with branches potentially having different starting points or
    methodologies, but ends up at the same point.
    The selection of the branch is essentially a "hyperparameter" that must be chosen first as the actual parameters to
    compile and run the code will vary depending on the branch selected.
    Examples of uses for this may be:
    * Running model simulations using different modeling frameworks (chirho, pyciemss, pysb) etc
        - Shared skills for loading data and handling results, but different intermediate skills for pre/post-processing
          the data and for running the simulation
    * Loading data from different sources
    """
    pass
# Branch in branching skill tree chosen by "hyperparameter"


class SkillTreeNode(BaseModel):
    """
    A node in a SkillTree.
    The id should be unique across all trees defined in the context.
    """
    id: UUIDField
    skill: Skill
    parents: list[Self]
    variable_values: TemplateVariableDict = None

    @property
    def inputs(self) -> typing.Iterable[SkillInputOutput]:
        seen = set()
        for input in itertools.chain(self.skill.inputs, *(parent.inputs for parent in self.parents)):
            if input.variable not in seen:
                yield input
            seen.add(input.variable)
        return itertools.chain(self.skill.inputs, *(parent.inputs for parent in self.parents))

    @property
    def variables(self) -> typing.Iterable[SkillInputOutput]:
        seen = set()
        for variable in itertools.chain(self.skill.variables, *(parent.variables for parent in self.parents)):
            if variable.id not in seen:
                yield variable
            seen.add(variable.id)

    @property
    def resolved(self) -> bool:
        return all(output.resolved for output in self.skill.outputs)

    def resolve(self) -> bool:
        if self.resolved:
            return True

        # Ensure all upstream requirements are resolved
        for parent in self.parents:
            if not parent.resolved:
                parent.resolve()

        return self.skill.resolve()


PlanStatus = typing.Literal["new", "ready", "in_progress", "success", "error"]

class ResolutionPlan(BaseModel):
    """
    Concrete set of steps to be performed, compiled from a SkillTree.
    This handles the actual execution of code, including any errors that may occur.
    A plan may be split into multiple steps, because it may be required for the agent to use the output of one step to
    determine/modify/create inputs for subsequent steps.
        For example: a "image evaluation" skill may need to first download and inspect an image file to determine what
        filetype the image is so that the filetype can be passed as an input as the next step of a plan.
    """
    steps: "list[ResolutionPlanStep]"
    owned_vars: list[SkillInputOutput]
    error: BaseException | None

    # Pydantic configuration option to allow storage of exceptions in the model
    model_config = ConfigDict(arbitrary_types_allowed=True)


PlanStepComponent: typing.TypeAlias = SkillTree | Skill
PlanStepStatus = typing.Literal["new", "ready", "in_progress", "success", "error"]

class ResolutionPlanStep(BaseModel):
    """
    A set of code, inputs, and outputs, compiled from a set of Skills and/or SkillTrees.
    The inputs will be a full set of inputs from all skills that are not provided by an upstream parent.
    The outputs will be a full set of outputs from all skills included in the step.
    "code" will be a single string that contains all of the source code from all included skills.
    Essentially, each step can be considered as a single "code cell" in the notebook, with the agent potentially
    using the output of this code cell to make decisions about how to run code in later code cells.
    """
    components: list[PlanStepComponent]
    inputs: list[SkillInputOutput]
    outputs: list[SkillInputOutput]
    code: str
    status: PlanStepStatus
    error: BaseException | None

    # Pydantic configuration option to allow storage of exceptions in the model
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ResolutionPlanComponent(BaseModel):
    """
    Reference to a Skill, the tree it is part of (if applicable), and the lines in the step source.
    If an error occurs, this (hopefully) allows the agent to identify the individual skill that failed so that the
    failing skill can be fixed, quarantined, replaced, etc.
    Probably also useful to humans for debugging.
    """
    target: Skill
    parent_tree: SkillTree | None
    code_lines: tuple[int, int]


# Classes for communicating with

class ErrorResponse(BaseModel):
    error: str

class SkillResponse(BaseModel):
    skill_id: IDType
    variable_values: TemplateVariableDict
    parents: list[Self]

class AgentResponse(BaseModel):
    item_type: typing.Literal['Skill', 'Error']
    item: SkillResponse | ErrorResponse



# Built-in skills
