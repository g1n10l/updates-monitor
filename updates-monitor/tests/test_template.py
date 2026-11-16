#!/usr/bin/env python3
"""Verify item/agent contract and Zabbix preprocessing of invalid results."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'zabbix-updates-monitor.json').read_text())['zabbix_export']
items = {i['key']: i for i in data['templates'][0]['items']}
required = {'regular', 'security', 'kernel_security'}
for key in required:
    item = items['updates.monitor.' + key]
    assert item['master_item']['key'] == 'updates.monitor.raw'
    js = item['preprocessing'][0]['parameters'][0]
    harness = 'var f = new Function("value", process.argv[1]); console.log(JSON.stringify(f(process.argv[2])));'
    valid = subprocess.check_output(['node', '-e', harness, js, json.dumps({'valid': 1, key: 4})], text=True).strip()
    invalid = subprocess.check_output(['node', '-e', harness, js, json.dumps({'valid': 0, key: 0})], text=True).strip()
    assert valid == '4' and invalid == 'null', (key, valid, invalid)
    trigger = next(t for t in data['triggers'] if '/updates.monitor.' + key + ')>0' in t['expression'])
    assert '{ITEM.VALUE1}' in trigger['event_name'] and '{ITEM.LASTVALUE1}' in trigger['opdata']
    assert 'Suma wyników kontroli' in trigger['opdata']
    assert '/updates.monitor.' + key + ')=0' in trigger['recovery_expression']
for field in ('valid', 'scheduler_active', 'service_state', 'service_failed', 'interval_seconds', 'updated_at'):
    item = items['updates.monitor.health.' + field]
    assert item['master_item']['key'] == 'updates.monitor.health'
    assert item['preprocessing'][0]['parameters'] == ['$.' + field]
agent = (ROOT / 'debian/agent.conf').read_text()
assert 'UserParameter=updates.monitor.raw,' in agent and 'UserParameter=updates.monitor.health,' in agent
assert any('Harmonogram sprawdzania aktualizacji jest wyłączony' == t['name'] for t in data['triggers'])
assert any('Wynik sprawdzania aktualizacji jest nieaktualny' == t['name'] for t in data['triggers'])
print('OK: klucze agenta, trzy liczniki, błędy i aktualność harmonogramu')
