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
    type: typing.Type[TemplateVarType]
    default: TemplateVarType | None = None # TODO: Figure out how well this (the typing) works and how to store arbitrary defaults a in sqlite db


class SkillInputOutput(BaseModel):  # TODO: Better name?
    """
    Things that need to exist in the environment so that the skill can use it or that a skill produces.
    Can be used to create a tree allowing skills to be chained together.
    """
    display_name: str
    description: str
    type: typing.Type  # Aware of submodules and/or alternative types
    resolved: bool = False
    env_variable: str | None = None
    template_variable: TemplateVariable | None = None

    @property
    def varname(self):
        return self.variable.template_var if self.variable else None


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
    id: SkillId
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
    """

    A collection of skills that work to
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
    pass
# Branch in branching skill tree chosen by "hyperparameter"


TreeNodeId: typing.TypeAlias = str

class SkillTreeNode(BaseModel):
    """
    """
    id: TreeNodeId
    # tree: SkillTree
    skill: Skill
    parents: list[Self]

    @property
    def inputs(self) -> typing.Iterable[SkillInputOutput]:
        return itertools.chain((parent.outputs for parent in self.parents))

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


PlanStepComponent: typing.TypeAlias = SkillTree | Skill
PlanStepStatus = typing.Literal["new", "ready", "in_progress", "success", "error"]

class ResolutionPlanStep(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    components: list[PlanStepComponent]
    inputs: list[SkillInputOutput]
    outputs: list[SkillInputOutput]
    code: str
    status: PlanStepStatus
    # error: BaseException | None
    error: BaseException | None


PlanStatus = typing.Literal["new", "ready", "in_progress", "success", "error"]

class ResolutionPlan(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    steps: list[ResolutionPlanStep]
    owned_vars: list[SkillInputOutput]
    error: BaseException | None
