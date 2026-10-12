"""Six local tools. stdout belongs to MCP; no prints or external effectors."""
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from .engine import Store
from .models import Name,Problem,Observation
from .example import example_problem

GUIDE='''Blue EFE is one-step numerical decision support using the v0.4 finite Bayesian core.
Use efe_example for a synthetic model schema; use efe_create for a real decision with explicitly
declared assumptions, cost units and either synthetic, assumed or caller_calibrated status.
Call efe_plan, execute ONLY an action allowed by the user/host, then efe_observe with the
returned revision and an event ID. Observation indices follow the chosen action's labels.
Record the actual observation or an acquisition failure. Never invent tool receipts or success.
Use the same event ID and identical payload to retry; different payload is rejected.
Get the current revision again before submitting a later observation. efe_plan itself is read-only.
Use one serial host executor per session. Planning does not reserve an action; two parallel
callers could both execute it outside this server. Revision guards only the belief ledger.
Budget tracks accepted modeled costs; it is not a hard cap on external spend or telemetry.
If action is null, use terminal; STOP:insufficient_evidence is an abstention, not an answer.
STOP:model_mismatch requires an explicitly revised model in a new session. Export the old
history first and describe the revision; do not blindly reuse old evidence as independent.
efe_inspect returns the model and audit trail; efe_close frees its memory.
Likelihoods and cost/loss units are caller supplied. References/hashes/calibration claims are
not checked against source files by this MCP. Use an authorized external reader/verifier.
Known dependent actions must share a group. Unknown correlations remain unmodeled.
Accepted failure, duplicate-source or impossible observations cost the selected action once.
Information mode measures nats and cost_multiplier converts cost into nats; risk mode converts
cost into loss units. Do not compare these scales without defining that conversion.
No network, file read/write, paid model call or vault access occurs in tool execution.
Sessions exist only in this stdio server process: clients do not share sessions and a restart
loses state. The host can save efe_inspect output if the user authorizes a destination.
An available MCP tool does not force the host to call it for every chat or task.
'''

store=Store()
mcp=FastMCP('Blue EFE',instructions=GUIDE,log_level='WARNING')
READ=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False)
WRITE=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False)
UPDATE=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=True,openWorldHint=False)


@mcp.tool(annotations=READ)
def efe_example()->dict:
    """Get a complete synthetic input and expected first choice. Not real calibration."""
    return dict(problem=example_problem(),expected_first_action='read',
                example_observation=1,expected_posterior=[.01,.99],
                label='SYNTHETIC demo, not real-world performance')


@mcp.tool(annotations=WRITE)
def efe_create(problem:Problem)->dict:
    """Create a finite Bayesian decision model. Declare assumptions; no external actions occur."""
    return store.create(problem)


@mcp.tool(annotations=READ)
def efe_plan(session_id:Name)->dict:
    """Choose one available context action or terminal decision from current belief and costs.

    This recommendation grants no permission and spends no budget. The host performs an
    authorized action, then returns its real observation with efe_observe.
    """
    return store.plan(session_id)


@mcp.tool(annotations=UPDATE)
def efe_observe(event:Observation)->dict:
    """Record a real observation or failure for the recommended action; charge once and update.

    Revision prevents stale changes. Exact event retries are idempotent. Caller source
    references are metadata, not independently verified evidence. Groups prevent known reuse.
    """
    return store.observe(event)


@mcp.tool(annotations=READ)
def efe_inspect(session_id:Name)->dict:
    """Return belief, costs, full model and audit history for inspection/export by the host."""
    return store.inspect(session_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=True,idempotentHint=True,openWorldHint=False))
def efe_close(session_id:Name)->dict:
    """Delete this in-memory session. Inspect/export first if its audit trail is needed."""
    return store.close(session_id)


@mcp.resource('efe://guide')
def guide()->str:
    return GUIDE


def main():
    mcp.run(transport='stdio')


if __name__=='__main__':main()
