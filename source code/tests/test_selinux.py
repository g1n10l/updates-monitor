"""Regression checks for monitoring after SELinux tools have been removed."""
import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    enforce = base / 'enforce'
    tool = base / 'restorecon'
    runtime = base / 'run'
    def mapped_path(value):
        return {'/sys/fs/selinux/enforce': enforce,
                '/usr/sbin/restorecon': tool}.get(str(value), Path(value))
    for name, writer in [('updates-monitor.py', 'write_state'),
                         ('updates-monitor-scheduler.py', 'atomic')]:
        tree = ast.parse((ROOT / name).read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('restore_context', writer)]
        assert len(nodes) == 2
        run = Mock()
        context = dict(Path=mapped_path, os=os, tempfile=tempfile, json=json,
                       subprocess=type('Commands', (), {'run': run}),
                       STATE=runtime/'state.json', RUNTIME=runtime)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), name, 'exec'), context)
        def write():
            if writer == 'write_state':
                context[writer]({'valid': 1})
            else:
                context[writer](runtime/'health.json', '{"valid":1}')
        for state, available in [(None, False), ('0', False), ('0', True), ('1', True)]:
            if enforce.exists(): enforce.unlink()
            if tool.exists(): tool.unlink()
            if state is not None: enforce.write_text(state)
            if available: tool.touch()
            run.reset_mock()
            write()
            assert run.call_count == (2 if state is not None and available else 0), (name,state,available)
        enforce.write_text('1'); tool.unlink(); run.reset_mock()
        run.side_effect = FileNotFoundError('restorecon unavailable')
        try:
            write()
        except FileNotFoundError:
            pass
        else:
            raise AssertionError('Enforcing must fail when restorecon is missing')
        run.side_effect = None
        print('OK runtime:', name)
    source = (ROOT / 'debian/postinst').read_text()
    block = source[source.index('selinux_tools=0'):source.index('\nfor config in ', source.index('selinux_tools=0'))]
    block = block.replace('/sys/fs/selinux/enforce', str(enforce))
    bindir = base/'bin'; bindir.mkdir()
    (bindir/'cat').symlink_to('/bin/cat')
    log = base/'log'
    for state, available, expected in [(None, False, 0), ('0', False, 0), ('1', False, 1), ('0', True, 0), ('1', True, 0)]:
        if enforce.exists(): enforce.unlink()
        if state is not None: enforce.write_text(state)
        for cmd in ['semanage','restorecon']:
            p=bindir/cmd
            if p.exists(): p.unlink()
            if available:
                p.write_text('#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$TEST_LOG"\n')
                p.chmod(0o755)
        result=subprocess.run(['/bin/sh','-c','set -eu\nfound=1\n'+block],env=dict(os.environ,PATH=str(bindir),TEST_LOG=str(log)),capture_output=True,text=True)
        assert result.returncode==expected,(state,available,result.stderr)
    print('OK postinst: disabled, permissive without tools, enforcing failure, tools available')
