"""Atomic in-memory sessions. No filesystem, network, subprocess or provider calls."""
from copy import deepcopy
from dataclasses import dataclass,field
import threading
import uuid
from .core import bayes
from .models import Problem,Observation

LIMITATIONS=[
    'One-step decision support, not a full-horizon planner or permission grant.',
    'Posterior is conditional on caller-supplied likelihoods and independence assumptions.',
    'Source references/hashes and calibration are caller assertions, not verified by this MCP.',
    'No external actions are executed. Sessions disappear when this server process exits.',
]


@dataclass
class Session:
    problem:Problem
    belief:list
    revision:int=0
    spent:float=0.
    used:set=field(default_factory=set)
    groups:set=field(default_factory=set)
    sources:set=field(default_factory=set)
    digests:set=field(default_factory=set)
    events:dict=field(default_factory=dict)
    history:list=field(default_factory=list)
    stopped:str|None=None


class Store:
    def __init__(self,max_sessions=64):
        self.sessions={}
        self.max_sessions=max_sessions
        self.lock=threading.RLock()

    def _get(self,sid):
        if sid not in self.sessions:raise ValueError('Unknown session; process may have restarted. Create a new model.')
        return self.sessions[sid]

    def create(self,problem):
        problem=Problem.model_validate(problem.model_dump())
        with self.lock:
            if len(self.sessions)>=self.max_sessions:raise ValueError('Session limit reached; inspect/export then close unused sessions')
            sid=str(uuid.uuid4())
            self.sessions[sid]=Session(problem,list(problem.prior))
            return self.inspect(sid)

    def inspect(self,sid):
        with self.lock:
            s=self._get(sid)
            return deepcopy(dict(session_id=sid,revision=s.revision,belief=s.belief,
                states=s.problem.states,spent=s.spent,budget_remaining=max(0.,s.problem.budget-s.spent),
                used_actions=sorted(s.used),used_groups=sorted(s.groups),stopped=s.stopped,
                model_status=s.problem.model_status,problem=s.problem.model_dump(),history=s.history,
                limitations=LIMITATIONS,source_verification='caller_asserted_only'))

    def plan(self,sid):
        with self.lock:
            s=self._get(sid)
            result=dict(session_id=sid,revision=s.revision,belief=list(s.belief),
                        mode=s.problem.mode,cost_unit=s.problem.cost_unit,model_status=s.problem.model_status,
                        budget_remaining=max(0.,s.problem.budget-s.spent),
                        requires_host_execution=False,limitations=list(LIMITATIONS))
            if s.stopped:
                return dict(result,action=None,terminal=s.stopped,scores=[],reason='model_mismatch')
            choice=s.problem.controller().choose(s.belief,[a.to_action() for a in s.problem.actions],
                used=s.used,groups=s.groups,budget=max(0.,s.problem.budget-s.spent))
            action=next((a.model_dump() for a in s.problem.actions if choice.action and a.id==choice.action.id),None)
            result.update(action=action,terminal=choice.terminal,scores=list(choice.scores),
                          terminal_risk=choice.terminal_risk,reason=choice.reason,
                          requires_host_execution=action is not None)
            return result

    def observe(self,event):
        event=Observation.model_validate(event.model_dump())
        with self.lock:
            s=self._get(event.session_id)
            payload=event.model_dump()
            if event.event_id in s.events:
                old=s.events[event.event_id]
                if old['payload']!=payload:raise ValueError('Event ID already used with different input')
                return dict(self.inspect(event.session_id),already_applied=True,event_revision=old['revision'])
            if event.expected_revision!=s.revision:raise ValueError('Stale revision; inspect current session before updating')
            plan=self.plan(event.session_id)
            if plan['action'] is None or plan['action']['id']!=event.action_id:
                raise ValueError('Observation must belong to the currently recommended available action')
            spec=next(a for a in s.problem.actions if a.id==event.action_id)
            if event.observation is not None and event.observation>=len(spec.observation_labels):
                raise ValueError('Observation index outside this action alphabet')
            prior=list(s.belief)
            posterior=prior
            stopped=None
            duplicate=(event.source_ref in s.sources or
                       event.content_sha256 is not None and event.content_sha256 in s.digests)
            if event.failure is not None:status='acquisition_failed'
            elif duplicate:status='duplicate_evidence_ignored'
            else:
                try:
                    posterior=list(bayes(prior,spec.to_action(),event.observation))
                    status='posterior_updated'
                except ValueError:
                    status='model_mismatch'
                    stopped='STOP:model_mismatch'
            # All validation precedes mutation. Accepted observations/failures cost once.
            s.spent+=spec.cost
            s.revision+=1
            s.belief=posterior
            s.stopped=stopped
            s.used.add(spec.id)
            s.groups.add(spec.group)
            if event.failure is None:
                s.sources.add(event.source_ref)
                if event.content_sha256:s.digests.add(event.content_sha256)
            s.history.append(dict(revision=s.revision,action=spec.id,kind=spec.kind,
                prior=prior,posterior=posterior,event_id=event.event_id,observation=event.observation,
                source_ref=event.source_ref,content_sha256=event.content_sha256,
                provenance_status='caller_asserted_only',group=spec.group,status=status,
                failure=event.failure,cost=spec.cost,total_cost=s.spent,scores=plan['scores']))
            s.events[event.event_id]=dict(payload=payload,revision=s.revision)
            return dict(self.inspect(event.session_id),already_applied=False,event_revision=s.revision)

    def close(self,sid):
        with self.lock:
            return dict(closed=self.sessions.pop(sid,None) is not None)
