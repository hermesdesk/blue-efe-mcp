"""Synthetic demo only; reliability is not a measured property of real sources."""
def example_problem():
    actions=[]
    for id,kind,reliability,cost in [('read','VAULT_READ',.99,.02),('ask','ASK',.9,.1),('search','SEARCH/VERIFY',.85,.08)]:
        actions.append(dict(id=id,kind=kind,description='Synthetic '+id+' fixture; host supplies result',
                            observation_labels=['unpaid_signal','paid_signal'],
                            likelihood=[[reliability,1-reliability],[1-reliability,reliability]],
                            cost=cost,group=id+'-origin'))
    return dict(task='Synthetic demo: determine fixture status',states=['unpaid','paid'],prior=[.5,.5],
                decisions=['ANSWER:unpaid','ANSWER:paid','STOP:insufficient_evidence'],
                losses=[[0.,1.],[1.,0.],[.25,.25]],actions=actions,budget=.2,
                cost_unit='illustrative effort points',model_status='synthetic',
                assumptions=['Synthetic symmetric likelihoods, not empirical calibration.',
                             'Different groups are assumed conditionally independent.'])
