"""Exact discrete inference. Information is in nats; costs in declared user units.

Eq. 1/2: predictive and Bayes. Prop. 3.3: information minus cost.
Theorem 3.4: terminal Bayes-risk reduction minus cost. Algorithm 1: choose,
observe, update, repeat. This module performs no external actions.
"""
from dataclasses import dataclass
import math


def distribution(p):
    p = tuple(float(x) for x in p)
    if not p or any(not math.isfinite(x) or x < 0 for x in p):
        raise ValueError('Probabilities must be finite and nonnegative')
    if not math.isclose(math.fsum(p), 1., abs_tol=1e-10, rel_tol=1e-10):
        raise ValueError('Probabilities must sum to one')
    return p


@dataclass(frozen=True)
class Action:
    id: str
    kind: str
    likelihood: tuple  # rows = state, columns = observation
    cost: float
    group: str = ''  # dependent/repeated evidence must share a group

    def __post_init__(self):
        rows = tuple(distribution(r) for r in self.likelihood)
        if not self.id or not self.kind or not rows or len({len(r) for r in rows}) != 1:
            raise ValueError('Action requires identifiers and a rectangular likelihood')
        if not math.isfinite(self.cost) or self.cost < 0:
            raise ValueError('Cost must be finite and nonnegative')
        object.__setattr__(self, 'likelihood', rows)


def predictive(q, action):
    q = distribution(q)
    if len(q) != len(action.likelihood):
        raise ValueError('Belief and likelihood state dimensions differ')
    return tuple(math.fsum(q[x]*action.likelihood[x][o] for x in range(len(q)))
                 for o in range(len(action.likelihood[0])))


def bayes(q, action, observation):
    pred = predictive(q, action)
    if not isinstance(observation, int) or not 0 <= observation < len(pred):
        raise ValueError('Unknown observation')
    z = pred[observation]
    if z <= 0:
        raise ValueError('Impossible observation: model revision required; posterior unchanged')
    return tuple(q[x]*action.likelihood[x][observation]/z for x in range(len(q)))


def entropy(q):
    return -math.fsum(p*math.log(p) for p in distribution(q) if p > 0)


def outcomes(q, action):
    return [(o, p, bayes(q, action, o)) for o,p in enumerate(predictive(q,action)) if p > 0]


def information(q, action):
    return max(0., entropy(q)-math.fsum(p*entropy(post) for _,p,post in outcomes(q,action)))


def risk(q, losses):
    q = distribution(q)
    if not losses or any(len(row) != len(q) for row in losses):
        raise ValueError('Loss matrix must be decision by state')
    if any(not math.isfinite(v) for row in losses for v in row):
        raise ValueError('Loss must be finite')
    values = [math.fsum(p*l for p,l in zip(q,row)) for row in losses]
    best = min(range(len(values)),key=values.__getitem__)
    return values[best], best


def preference_efe(q, action, preferences):
    """Eq. 6, restricted to deterministic measurements; excludes explicit cost.

    Preference probabilities must be on the same observation alphabet. Flat
    preferences of different alphabet sizes have different normalizers; do not
    treat those raw risks as a common constant. Prefer information mode for OQA.
    """
    preferences = distribution(preferences)
    pred = predictive(q,action)
    if len(preferences) != len(pred) or any(p <= 0 for p in preferences):
        raise ValueError('Strictly positive observation preferences required')
    if any(sum(v > 0 for v in row) != 1 for row in action.likelihood):
        raise ValueError('This Eq. 6 helper is restricted to deterministic observations')
    return -math.fsum(p*math.log(v) for p,v in zip(pred,preferences))-information(q,action)


@dataclass(frozen=True)
class Choice:
    action: Action | None
    terminal: str | None
    scores: tuple
    terminal_risk: float
    reason: str


class Controller:
    """One-step policy. Not a full-horizon planner. Ties favor stopping.

    information mode is the entropy objective of Prop. 3.3.
    risk mode uses the supplied finite loss matrix (Theorem 3.4).
    Available actions are proposed by the caller, never by the hidden target.
    """
    def __init__(self, losses=None, decisions=None, mode='risk', lam=1.):
        if mode not in ('risk','information') or not math.isfinite(lam) or lam < 0:
            raise ValueError('Invalid mode or cost multiplier')
        if losses is not None:
            losses = tuple(tuple(float(x) for x in row) for row in losses)
            if not losses or not losses[0]: raise ValueError('Empty losses')
            risk((1/len(losses[0]),)*len(losses[0]), losses)
            if decisions is None or len(decisions) != len(losses):
                raise ValueError('A terminal name is required for each loss row')
            if any(not isinstance(d,str) or not d.strip() for d in decisions) or len(set(decisions))!=len(decisions):
                raise ValueError('Terminal names must be unique nonempty strings')
        elif decisions is not None:
            raise ValueError('Decisions require a loss matrix')
        self.losses, self.decisions, self.mode, self.lam = losses, decisions, mode, lam

    def choose(self, q, actions, *, used=(), groups=(), budget=math.inf):
        q = distribution(q)
        if math.isnan(budget) or budget < 0: raise ValueError('Invalid budget')
        if len({a.id for a in actions}) != len(actions): raise ValueError('Duplicate action ID')
        losses = self.losses or tuple(tuple(float(i != j) for j in range(len(q))) for i in range(len(q)))
        terminal_risk, best_d = risk(q, losses)
        terminal = self.decisions[best_d] if self.decisions else f'ANSWER:{best_d}'
        now = entropy(q) if self.mode == 'information' else terminal_risk
        scores, winner, best = [], None, 0.
        for a in actions:
            if a.id in used or (a.group and a.group in groups) or a.cost > budget + 1e-12:
                continue
            obs = outcomes(q,a)
            expected_risk = math.fsum(p*risk(post,losses)[0] for _,p,post in obs)
            ig = max(0.,entropy(q)-math.fsum(p*entropy(post) for _,p,post in obs))
            after = now-ig if self.mode == 'information' else expected_risk
            value = now-after
            net = value-self.lam*a.cost
            scores.append(dict(action=a.id, kind=a.kind, information_nats=ig,
                               expected_terminal_risk=expected_risk, context_value=value,
                               cost=a.cost, weighted_cost=self.lam*a.cost, net_value=net,
                               objective_after=after+self.lam*a.cost))
            if net > best + 1e-12:
                winner,best = a,net
        return Choice(winner, None if winner else terminal, tuple(scores),terminal_risk,
                      'positive_context_value' if winner else 'no_available_positive_value')
