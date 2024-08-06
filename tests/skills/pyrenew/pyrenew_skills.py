from beaker_bunsen.skills.model import Skill, SkillTree, SkillTreeNode, SkillInputOutput, TemplateVariable


generation_interval = SkillInputOutput(
    display_name="Generation Interval",
    description="",
    type="pyrenew.deterministic.DeterministicPMF",
    env_variable="gen_int",
    template_variable_base="gen_int",
)

pmf_array = SkillInputOutput(
    display_name="probability_mass_function",  # TODO: Check if this is correct
    description="",
    type="jnp.array",
)

I0 = SkillInputOutput(
    display_name="I0 (initial infections)",
    description="",
    type="pyrenew.deterministic.DeterministicPMF",
    env_variable="I0",
    template_variable_base="I0",
)

new_generation_interval = Skill(
    display_name="New deterministic generation interval",
    description="",
    required_imports=["import jax.numpy as jnp", "from pyrenew.deterministic import DeterministicPMF"],
    variables=[
        TemplateVariable(
            variable="pmf_values",
            description="PMF array values",
            display_name="Probabily Mass Function array values",
            type="list[float]",
            default=[0.4, 0.3, 0.2, 0.1],
        )
    ],
    inputs=[],
    outputs=[
        pmf_array,
        generation_interval
    ],
    language="python3",
    source="""
# (1) The generation interval (deterministic)
{{ pmf_array }} = jnp.array({{ pmf_values }})
{{ gen_int }} = DeterministicPMF(name="{{ gen_int }}", value={{ pmf_array }})
""".strip(),
)

define_intitial_infections = Skill(
    display_name="Define initial infections",
    description="",
    required_imports=["import numpyro.distributions as dist", "from pyrenew.deterministic import DeterministicPMF"],
    variables=[
        TemplateVariable(
            variable="I0_distribution",
            display_name="I0 distribution",
            description="distribution for I0",
            type="numpyro.distributions.distribution.Distribution",
            default="dist.LogNormal(2.5, 1)",
        )
    ],
    inputs=[
        pmf_array,
    ],
    outputs=[
        I0,
    ],
    language="python3",
    source="""
# (2) Initial infections (inferred with a prior)
{{ I0 }} = InfectionInitializationProcess(
    "I0_initialization",
    DistributionalRV(name="{{ I0 }}", dist={{ I0_distribution }}),
    InitializeInfectionsZeroPad({{ pmf_array }}.size),
    t_unit=1,
)
""".strip(),
)

model = SkillInputOutput(
    display_name="model",
    description="",
    env_variable="model",
    template_variable_base="model",
    type="pyrenew.metaclass.Model",
)
rt_proc = SkillInputOutput(
    display_name="rt_proc",
    description="Procedure that generates a sample for values of R at different timesteps t",
    env_variable="rt_proc",
    template_variable_base="rt_proc",
    type="pyrenew.metaclass.RandomVariable",
)
latent_infections = SkillInputOutput(
    display_name="latent_infections",
    description="",
    env_variable="latent_infections",
    template_variable_base="latent_infections",
    type="pyrenew.latent.Infections",

)
observation_process = SkillInputOutput(
    display_name="observation_process",
    description="",
    env_variable="observation_process",
    template_variable_base="observation_process",
    type="pyrenew.metaclass.RandomVariable",

)

define_rt_proc = Skill(
    display_name="rt_proc",
    description="",
    required_imports=[
        "import numpyro.distributions as dist",
        "from pyrenew.process import SimpleRandomWalkProcess",
        "import numpyro",
        "from pyrenew.metaclass import TransformedRandomVariable",
        "from pyrenew.metaclass import DistributionalRV",
        "from pyrenew.metaclass import RandomVariable",
        "import jax.numpy as jnp",
    ],
    variables=[],
    inputs=[],
    outputs=[rt_proc],
    language="python3",
    source="""
# (3) The random walk on log Rt, with an inferred s.d. Here, we
# construct a custom RandomVariable.
class MyRt(RandomVariable):

    def validate(self):
        pass

    def sample(self, n_steps: int, **kwargs) -> tuple:
        sd_rt = numpyro.sample("Rt_random_walk_sd", dist.HalfNormal(0.025))

        rt_rv = TransformedRandomVariable(
            "Rt_rv",
            base_rv=SimpleRandomWalkProcess(
                name="log_rt",
                step_rv=DistributionalRV(
                    name="rw_step_rv",
                    dist=dist.Normal(0, sd_rt),
                    reparam=LocScaleReparam(0),
                ),
                init_rv=DistributionalRV(
                    name="init_log_rt",
                    dist=dist.Normal(jnp.log(1), jnp.log(1.2)),
                ),
            ),
            transforms=t.ExpTransform(),
        )
        return rt_rv.sample(n_steps=n_steps, **kwargs)


{{ rt_proc }} = MyRt()
""".strip(),
)
define_latent_infections = Skill(
    display_name="latent_infections",
    description="",
    required_imports=["from pyrenew.latent import Infections"],
    variables=[],
    inputs=[],
    outputs=[latent_infections],
    language="python3",
    source="""
{{ latent_infections }} = Infections()
""".strip(),
)
define_observation_process = Skill(
    display_name="observation_process",
    description="",
    required_imports=["from pyrenew.observation import PoissonObservation"],
    variables=[],
    inputs=[],
    outputs=[observation_process],
    language="python3",
    source="""
{{ observation_process }} = PoissonObservation("poisson_rv")
""".strip(),
)

define_renewal_model = Skill(
    display_name="Define a RtInfections Renewal Model",
    description="Defines a renewal model",
    required_imports=[],
    variables=[

    ],
    inputs=[
        generation_interval,
        I0,
        rt_proc,
        latent_infections,
        observation_process,
    ],
    outputs=[
        model
    ],
    language="python3",
    source="""
{{ model }} = RtInfectionsRenewalModel(
    gen_int_rv={{ gen_int }},
    I0_rv=i{{ I0 }},
    Rt_process_rv={{ rt_proc }},
    latent_infections_rv={{ latent_infections  }},
    infection_obs_process_rv={{ observation_process }} ,
)
""".strip(),

)

gen_int_node = SkillTreeNode(
    skill=new_generation_interval,
    parents=[],
)

build_renewal_model = SkillTree(
    display_name="Build renewal model",
    description="Builds a new renewal model from scratch",
    head=SkillTreeNode(
        skill=define_renewal_model,
        parents=[
            SkillTreeNode(
                skill=define_observation_process,
                parents=[],
            ),
            SkillTreeNode(
                skill=define_rt_proc,
                parents=[],
            ),
            SkillTreeNode(
                skill=define_latent_infections,
                parents=[],
            ),
            SkillTreeNode(
                skill=define_intitial_infections,
                parents=[
                    gen_int_node
                ],
            ),
            gen_int_node
        ]
    )
)
