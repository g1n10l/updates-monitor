#!/usr/bin/env python3
"""Test DNF classification and error handling without a live DNF installation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('redhat_check', root / 'redhat/check.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
responses = iter(['', 'curl.x86_64\nopenssl.x86_64\nkernel.x86_64\nkernel-core.x86_64\nkernel-modules.x86_64\n',
                  'openssl.x86_64\nkernel.x86_64\nkernel-core.x86_64\nopenssl.x86_64\n'])
module.query = lambda *args: next(responses)
with tempfile.TemporaryDirectory() as temp:
    module.STATE = Path(temp) / 'state.json'
    result = module.check()
    assert (result['regular'], result['security'], result['kernel_security'], result['valid']) == (1, 1, 3, 1), result
    module.STATE.write_text(json.dumps({'regular': 3, 'security': 2, 'kernel_security': 1,
                                        'valid': 0, 'checked_at': 1}))
    for count in (5, 8, 8, 3, 0):
        output = ''.join('pkg'+str(i)+'.x86_64\n' for i in range(count))
        responses = iter(['', output, ''])
        module.query = lambda *args: next(responses)
        current = module.check()
        assert [current[k] for k in ('regular', 'security', 'kernel_security')] == [count, 0, 0], current
        module.STATE.write_text(json.dumps(current))
assert module.candidates('') == set()
try:
    module.candidates('unexpected output with spaces')
except ValueError:
    pass
else:
    raise AssertionError('Nieprawidłowy wynik nie został odrzucony')
assert 'crond.service' in subprocess.check_output(['sed', 's/cron\\.service/crond.service/g', str(root / 'updates-monitor-scheduler.py')], text=True)
print('OK: klasyfikacja DNF, deduplikacja i nieprawidłowe wyniki')
