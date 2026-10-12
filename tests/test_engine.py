import copy
import unittest
from blue_efe_mcp.engine import Store
from blue_efe_mcp.models import Problem, Observation
from blue_efe_mcp.example import example_problem


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.store=Store()
        self.problem=Problem.model_validate(example_problem())
        self.session=self.store.create(self.problem)
        self.sid=self.session['session_id']

    def obs(self,**changes):
        data=dict(session_id=self.sid,expected_revision=0,action_id='read',event_id='e1',
                  observation=1,source_ref='fixture:receipt',content_sha256=None,failure=None)
        data.update(changes)
        return Observation.model_validate(data)

    def test_plan_matches_original_and_observe_then_stop(self):
        plan=self.store.plan(self.sid)
        self.assertEqual(plan['action']['id'],'read')
        self.assertAlmostEqual(plan['scores'][0]['net_value'],.22)
        self.assertEqual(self.store.inspect(self.sid)['revision'],0)
        state=self.store.observe(self.obs())
        self.assertAlmostEqual(state['belief'][1],.99)
        self.assertAlmostEqual(state['spent'],.02)
        self.assertEqual(self.store.plan(self.sid)['terminal'],'ANSWER:paid')

    def test_retries_are_idempotent_conflicting_event_rejected(self):
        self.store.observe(self.obs())
        again=self.store.observe(self.obs())
        self.assertTrue(again['already_applied'])
        self.assertEqual(again['revision'],1)
        self.assertEqual(len(again['history']),1)
        with self.assertRaises(ValueError):self.store.observe(self.obs(observation=0))
        self.assertAlmostEqual(self.store.inspect(self.sid)['spent'],.02)

    def test_stale_wrong_action_invalid_observation_do_not_mutate(self):
        for changes in ({'expected_revision':1},{'action_id':'ask'},{'observation':2}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.store.observe(self.obs(**changes))
        self.assertEqual(self.store.inspect(self.sid)['history'],[])

    def test_failure_costs_and_marks_action_consumed(self):
        r=self.store.observe(self.obs(observation=None,failure='timeout'))
        self.assertEqual(r['belief'],[.5,.5])
        self.assertAlmostEqual(r['spent'],.02)
        self.assertEqual(r['history'][0]['status'],'acquisition_failed')
        self.assertEqual(self.store.plan(self.sid)['action']['id'],'ask')

    def test_impossible_observation_stops_with_unchanged_posterior(self):
        p=example_problem();p['prior']=[1.,0.];p['actions'][0]['likelihood']=[[1.,0.],[0.,1.]]
        # This model would stop: impossible observations cannot be submitted after stop.
        sid=self.store.create(Problem.model_validate(p))['session_id']
        with self.assertRaises(ValueError):self.store.observe(self.obs(session_id=sid))
        p=example_problem();p['actions'][0]['observation_labels']=['no','yes','impossible']
        p['actions'][0]['likelihood']=[[.99,.01,0.],[.01,.99,0.]]
        sid=self.store.create(Problem.model_validate(p))['session_id']
        r=self.store.observe(self.obs(session_id=sid,observation=2))
        self.assertEqual(r['belief'],[.5,.5])
        self.assertEqual(self.store.plan(sid)['terminal'],'STOP:model_mismatch')
        self.assertAlmostEqual(r['spent'],.02)

    def test_budget_and_known_correlated_groups(self):
        p=example_problem();p['budget']=.01
        sid=self.store.create(Problem.model_validate(p))['session_id']
        self.assertEqual(self.store.plan(sid)['terminal'],'STOP:insufficient_evidence')
        p=example_problem()
        for a in p['actions']:a['group']='common-origin'
        sid=self.store.create(Problem.model_validate(p))['session_id']
        self.store.observe(self.obs(session_id=sid,observation=None,failure='missing'))
        self.assertIsNone(self.store.plan(sid)['action'])

    def test_unknown_and_closed_sessions_and_isolation(self):
        other=self.store.create(self.problem)['session_id']
        self.store.observe(self.obs())
        self.assertEqual(self.store.inspect(other)['belief'],[.5,.5])
        self.store.close(self.sid)
        self.assertEqual(self.store.close(self.sid),{'closed':False})
        with self.assertRaises(ValueError):self.store.inspect(self.sid)

    def test_bounds(self):
        store=Store(max_sessions=1)
        store.create(self.problem)
        with self.assertRaises(ValueError):store.create(self.problem)

    def test_duplicate_source_costs_without_second_bayes_update(self):
        p=example_problem();p['mode']='information'
        for a in p['actions']:a['cost']=.001
        sid=self.store.create(Problem.model_validate(p))['session_id']
        first=self.store.observe(self.obs(session_id=sid))
        next_id=self.store.plan(sid)['action']['id']
        second=self.store.observe(self.obs(session_id=sid,expected_revision=1,action_id=next_id,event_id='e2'))
        self.assertEqual(second['belief'],first['belief'])
        self.assertEqual(second['history'][-1]['status'],'duplicate_evidence_ignored')
        self.assertAlmostEqual(second['spent'],.002)

    def test_concurrent_stale_updates_do_not_both_apply(self):
        from concurrent.futures import ThreadPoolExecutor
        def submit(e):
            try:return self.store.observe(self.obs(event_id=e))
            except ValueError:return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(submit,['e1','e2']))
        self.assertEqual(sum(x is not None for x in results),1)
        self.assertEqual(self.store.inspect(self.sid)['revision'],1)

    def test_validation_rejects_bad_models(self):
        variants=[]
        for field,value in [('prior',[.8,.8]),('prior',[True,False]),('budget',float('nan')),
                            ('states',['paid','paid']),('assumptions',[])]:
            p=example_problem();p[field]=value;variants.append(p)
        p=example_problem();p['actions'][0]['likelihood']=[[1.],[1.]];variants.append(p)
        p=example_problem();p['actions'][0]['cost']=-1.;variants.append(p)
        p=example_problem();p['losses']=[[0.,1.]];variants.append(p)
        p=example_problem();p['actions'][1]['id']='read';variants.append(p)
        for p in variants:
            with self.subTest(p=p),self.assertRaises(ValueError):Problem.model_validate(p)

    def test_observation_xor_and_strict_integer(self):
        for changes in ({'observation':True},{'observation':None},{'failure':'oops'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.obs(**changes)

    def test_snapshot_not_mutable_alias(self):
        state=self.store.inspect(self.sid)
        state['belief'][0]=100
        state['problem']['states'].append('injected')
        self.assertEqual(self.store.inspect(self.sid)['belief'],[.5,.5])
        self.assertEqual(len(self.store.inspect(self.sid)['problem']['states']),2)

if __name__=='__main__':unittest.main()
