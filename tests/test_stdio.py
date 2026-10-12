"""Real client/server protocol test; launches an isolated stdio subprocess."""
import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
import unittest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client


@asynccontextmanager
async def client():
    # No inherited PYTHONPATH: validates launch.py or installed package behavior.
    launch=Path(__file__).resolve().parents[1]/'launch.py'
    assert launch.is_file(), 'MCP launch entry point has not been implemented'
    params=StdioServerParameters(command=sys.executable,args=[str(launch)],cwd=str(launch.parent))
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            yield session


def data(result):
    if result.isError:raise AssertionError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)


class StdioTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_protocol_round_trip_errors_and_resources(self):
        async with asyncio.timeout(30),client() as c:
            listed=await c.list_tools()
            names={t.name for t in listed.tools}
            self.assertEqual(names,{'efe_example','efe_create','efe_plan','efe_observe','efe_inspect','efe_close'})
            example=data(await c.call_tool('efe_example',{}))
            state=data(await c.call_tool('efe_create',{'problem':example['problem']}))
            sid=state['session_id']
            plan=data(await c.call_tool('efe_plan',{'session_id':sid}))
            self.assertEqual(plan['action']['id'],'read')
            invalid=await c.call_tool('efe_observe',{'event':dict(session_id=sid,expected_revision=0,
                action_id='read',event_id='bad',observation=True,source_ref='test:receipt')})
            self.assertTrue(invalid.isError)
            event=dict(session_id=sid,expected_revision=0,action_id='read',event_id='e1',
                       observation=1,source_ref='test:receipt')
            state=data(await c.call_tool('efe_observe',{'event':event}))
            self.assertAlmostEqual(state['belief'][1],.99)
            again=data(await c.call_tool('efe_observe',{'event':event}))
            self.assertTrue(again['already_applied'])
            self.assertAlmostEqual(again['spent'],.02)
            plan=data(await c.call_tool('efe_plan',{'session_id':sid}))
            self.assertEqual(plan['terminal'],'ANSWER:paid')
            log=data(await c.call_tool('efe_inspect',{'session_id':sid}))
            self.assertEqual(len(log['history']),1)
            resources=await c.list_resources()
            self.assertIn('efe://guide',{str(r.uri) for r in resources.resources})
            guide=await c.read_resource('efe://guide')
            self.assertIn('caller',guide.contents[0].text)
            closed=data(await c.call_tool('efe_close',{'session_id':sid}))
            self.assertTrue(closed['closed'])
            bad=await c.call_tool('efe_plan',{'session_id':sid})
            self.assertTrue(bad.isError)

    async def test_two_host_processes_do_not_share_sessions(self):
        async with asyncio.timeout(30),client() as a,client() as b:
            ex=data(await a.call_tool('efe_example',{}))
            sid=data(await a.call_tool('efe_create',{'problem':ex['problem']}))['session_id']
            self.assertTrue((await b.call_tool('efe_inspect',{'session_id':sid})).isError)

if __name__=='__main__':unittest.main()
