import itertools
import typing
from collections import deque
from pydantic import BaseModel, Field, ConfigDict, UUID4
from typing_extensions import Self
from uuid import uuid4

import jinja2


TemplateVarType = typing.TypeVar('TemplateVarType')

class TemplateVariable(BaseModel):
    """
    A definition of a template variable to be used in skill templates.

    A template variable may be used in multiple templates or multiple times in a single template.
    The id and template_var must be unique across all template variables defined within a context.
    """
    id: str = Field(default_factory=lambda: uuid4().hex)
    variable: str
    display_name: str
    description: str
    type: typing.Type[TemplateVarType] | str
    default: TemplateVarType | None = None # TODO: Figure out how well this (the typing) works and how to store arbitrary defaults a in sqlite db


class SkillInputOutput(BaseModel):  # TODO: Better name?
    """
    Things that need to exist in the environment so that the skill can use it or that a skill produces.
    Can be used to create a tree allowing skills to be chained together.
    """
    instance_count: typing.ClassVar[dict[str, int]] = {}

    display_name: str
    description: str
    type: typing.Type | str # Aware of submodules and/or alternative types
    resolved: bool = False
    env_variable: str | None = None
    template_variable_base: str | None = None
    template_variable: TemplateVariable | None = None

    def model_post_init(self, __context: typing.Any) -> None:
        if self.template_variable is None and self.template_variable_base is not None:
            # Update instance count for this variable
            instance_count = self.__class__.instance_count.get(self.template_variable_base, 0) + 1
            self.__class__.instance_count[self.template_variable_base] = instance_count

            # Build default template variable instance
            self.template_variable = TemplateVariable(
                variable=f"{self.template_variable_base}_{self.__class__.instance_count}",
                type=self.type,
                display_name=self.display_name,
                description=self.description,
            )
        return super().model_post_init(__context)

    @property
    def varname(self):
        return self.template_variable.variable if self.template_variable else None


SkillId: typing.TypeAlias = str

class Skill(BaseModel):
    """
    Basic unit of "work" consisting of a templated portion of code that can be executed by Bunsen.
    The skill may be executed by itself or combined into a larger set of code by combining multiple Skills into one
    codeset.
    Skills import and output SkillInputOutput items, which are annotated references to variables that exist in the
    environment. As the inputs and outputs are the same type, skills can be chained such that the output of an earlier
    skill can be used by another skill, either as part of the same "plan" or as part of a subsequent interaction.
    """
    id: SkillId = Field(default_factory=lambda: uuid4().hex)
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
            print(input, type(input))
            if input.display_name not in vars:
                vars[input.template_variable.variable] = input.env_variable
        for output in self.outputs:
            if output.display_name not in vars:
                vars[output.template_variable.variable] = output.env_variable
        return template.render(vars)


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
    display_name: str
    description: str
    head: "SkillTreeNode"
    # node_index: dict["TreeNodeId", "SkillTreeNode"]

    @property
    def nodes(self) -> typing.Iterable["SkillTreeNode"]:
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


TreeNodeId: typing.TypeAlias = str

class SkillTreeNode(BaseModel):
    """
    A node in a SkillTree.
    The id should be unique across all trees defined in the context.
    """
    id: TreeNodeId = Field(default_factory=lambda: uuid4().hex)
    skill: Skill
    parents: list[Self]

    @property
    def inputs(self) -> typing.Iterable[SkillInputOutput]:
        seen = set()
        for input in itertools.chain(self.skill.inputs, *(parent.inputs for parent in self.parents)):
            if input.env_variable not in seen:
                yield input
            seen.add(input.env_variable)
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
