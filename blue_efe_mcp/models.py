"""Strict, bounded tool input contracts. Labels and provenance are caller supplied."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .core import Action, Controller, distribution

Name=Annotated[str,Field(strict=True,min_length=1,max_length=128,pattern=r'.*\S.*')]
Text=Annotated[str,Field(strict=True,min_length=1,max_length=2000,pattern=r'.*\S.*')]
Number=Annotated[float,Field(strict=True,ge=0,le=1e12,allow_inf_nan=False)]
Probability=Annotated[float,Field(strict=True,ge=0,le=1,allow_inf_nan=False)]
Count=Annotated[int,Field(strict=True,ge=0,le=1024)]


class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid')


class ContextAction(StrictModel):
    id:Name
    kind:Name
    description:Text
    observation_labels:list[Name]=Field(min_length=1,max_length=32)
    likelihood:list[list[Probability]]=Field(min_length=1,max_length=64)
    cost:Number
    group:Name

    @model_validator(mode='after')
    def validate_action(self):
        if len(set(self.observation_labels))!=len(self.observation_labels):
            raise ValueError('Observation labels must be unique')
        if any(len(row)!=len(self.observation_labels) for row in self.likelihood):
            raise ValueError('Likelihood columns must match observation labels')
        self.to_action()
        return self

    def to_action(self):
        return Action(self.id,self.kind,tuple(map(tuple,self.likelihood)),self.cost,self.group)


class Problem(StrictModel):
    task:Text
    states:list[Name]=Field(min_length=2,max_length=64)
    prior:list[Probability]=Field(min_length=2,max_length=64)
    decisions:list[Name]=Field(min_length=1,max_length=64)
    losses:list[list[Number]]=Field(min_length=1,max_length=64)
    actions:list[ContextAction]=Field(max_length=32)
    budget:Number
    cost_unit:Name
    mode:Literal['risk','information']='risk'
    cost_multiplier:Number=1.
    model_status:Literal['synthetic','assumed','caller_calibrated']
    assumptions:list[Text]=Field(min_length=1,max_length=16)
    calibration_refs:list[Text]=Field(default_factory=list,max_length=16)

    @model_validator(mode='after')
    def validate_problem(self):
        if len(set(self.states))!=len(self.states) or len(self.prior)!=len(self.states):
            raise ValueError('States must be unique and match prior size')
        distribution(self.prior)
        if len(self.losses)!=len(self.decisions) or any(len(row)!=len(self.states) for row in self.losses):
            raise ValueError('Loss matrix must be decision by state')
        if len({a.id for a in self.actions})!=len(self.actions):
            raise ValueError('Duplicate action IDs')
        if any(len(a.likelihood)!=len(self.states) for a in self.actions):
            raise ValueError('Likelihood rows must match states')
        if self.model_status=='caller_calibrated' and not self.calibration_refs:
            raise ValueError('Caller-calibrated models require reference metadata')
        self.controller()
        return self

    def controller(self):
        return Controller(self.losses,self.decisions,self.mode,self.cost_multiplier)


class Observation(StrictModel):
    session_id:Name
    expected_revision:Count
    action_id:Name
    event_id:Name
    observation:Annotated[int,Field(strict=True,ge=0,le=31)]|None=None
    source_ref:Text
    content_sha256:Annotated[str,Field(pattern=r'^[0-9a-f]{64}$')]|None=None
    failure:Text|None=None

    @model_validator(mode='after')
    def exactly_one_result(self):
        if (self.observation is None)==(self.failure is None):
            raise ValueError('Supply either observation index or failure, exactly one')
        return self
