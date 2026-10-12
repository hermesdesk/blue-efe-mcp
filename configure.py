"""Write merge-ready snippets inside the package, never active host configuration."""
import argparse
import json
from pathlib import Path
import sys


def ps_quote(text):
    return "'"+str(text).replace("'","''")+"'"


def generate(python,out,root=None):
    root=Path(root or Path(__file__).parent).resolve()
    python=Path(python).resolve()
    launch=root/'launch.py'
    if not python.is_file() or not launch.is_file():raise ValueError('Interpreter and launch.py must exist')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    entry=dict(command=str(python),args=[str(launch)])
    toml='[mcp_servers.blue-efe]\ncommand = '+json.dumps(str(python),ensure_ascii=False)+'\nargs = '+json.dumps([str(launch)],ensure_ascii=False)+'\n'
    (out/'codex.toml').write_text(toml,encoding='utf-8')
    (out/'claude-desktop.json').write_text(json.dumps({'mcpServers':{'blue-efe':entry}},indent=2),encoding='utf-8')
    (out/'claude-code.json').write_text(json.dumps({'mcpServers':{'blue-efe':dict(type='stdio',**entry)}},indent=2),encoding='utf-8')
    command=' '.join([ps_quote(python),ps_quote(launch)])
    (out/'CONNECTION_COMMANDS.txt').write_text(
        '# PowerShell commands; run only when you want to register the server.\n'
        '# Review an existing blue-efe entry before replacing it.\n'
        'codex mcp add blue-efe -- '+command+'\n'
        'claude mcp add --transport stdio --scope user blue-efe -- '+command+'\n'
        '# Desktop: merge ONLY mcpServers.blue-efe from claude-desktop.json into your existing config.\n'
        '# Recreate these snippets after moving this directory or interpreter.\n',encoding='utf-8')
    return entry


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--python',type=Path,default=Path(sys.executable))
    p.add_argument('--out',type=Path,default=Path(__file__).parent/'config-generated')
    a=p.parse_args()
    generate(a.python,a.out)
    print('Connection snippets created at '+str(a.out.resolve())+'. No client settings were changed.')
