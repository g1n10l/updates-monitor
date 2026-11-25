#!/usr/bin/env python3
"""Verify item/agent contract and Zabbix preprocessing of invalid results."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'zabbix-updates-monitor.json').read_text())['zabbix_export']
items = {i['key']: i for i in data['templates'][0]['items']}
assert data['templates'][0]['template'] == 'updates-monitor'
assert data['templates'][0]['name'] == 'updates-monitor'
for trigger in data['triggers']:
    for key in ('expression', 'recovery_expression'):
        if key in trigger:
            assert '/Updates monitor Debian Ubuntu/' not in trigger[key]
            assert '/updates-monitor/' in trigger[key]

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
    assert trigger['event_name'] == trigger['name'] + ' ({ITEM.VALUE1})'
    assert '{ITEM.LASTVALUE1}' in trigger['opdata']
    assert item['preprocessing'][-1]['type'] == 'DISCARD_UNCHANGED'
    assert trigger['expression'] == 'last(/updates-monitor/updates.monitor.' + key + ')>0'
    assert trigger['type'] == 'MULTIPLE'
    assert {'tag': 'updates-monitor.scope', 'value': '{HOST.HOST}:' + key} in trigger['tags']
for field in ('valid', 'scheduler_active', 'service_state', 'service_failed', 'interval_seconds', 'updated_at'):
    item = items['updates.monitor.health.' + field]
    assert item['master_item']['key'] == 'updates.monitor.health'
    assert item['preprocessing'][0]['parameters'] == ['$.' + field]
agent = (ROOT / 'debian/agent.conf').read_text()
assert 'UserParameter=updates.monitor.raw,' in agent and 'UserParameter=updates.monitor.health,' in agent
assert any('Harmonogram sprawdzania aktualizacji jest wyłączony' == t['name'] for t in data['triggers'])
assert any('Wynik sprawdzania aktualizacji jest nieaktualny' == t['name'] for t in data['triggers'])
print('OK: klucze agenta, trzy liczniki, błędy i aktualność harmonogramu')

rule = json.loads((ROOT / 'zabbix-updates-monitor-correlation.json').read_text())
assert rule['filter']['evaltype'] == 1
assert rule['operations'] == [{'type': 0}]
conditions = rule['filter']['conditions']
assert {'type': 4, 'tag': 'updates-monitor.component', 'operator': 0, 'value': 'package-count'} in conditions
assert {'type': 5, 'tag': 'updates-monitor.component', 'operator': 0, 'value': 'package-count'} in conditions
assert {'type': 3, 'oldtag': 'updates-monitor.scope', 'newtag': 'updates-monitor.scope'} in conditions

assert 'updates.monitor.total' not in items

for field in ('available', 'current', 'target', 'error'):
    item = items['updates.monitor.dist_upgrade.' + field]
    js = item['preprocessing'][0]['parameters'][0]
    for payload, expected in [({'valid': 1, 'dist_upgrade_available': 1, 'dist_upgrade_' + field: 1 if field == 'available' else 'test'}, '1' if field == 'available' else '"test"'),
                              ({'valid': 0}, 'null'), ({'valid': 1}, 'null')]:
        actual = subprocess.check_output(['node', '-e', harness, js, json.dumps(payload)], text=True).strip()
        assert actual == expected, (field, actual, expected)
trigger = next(t for t in data['triggers'] if t['name'] == 'Dostępna aktualizacja dystrybucji')
assert trigger['priority'] == 'WARNING'
assert '/updates.monitor.dist_upgrade.available)=1' in trigger['expression']
assert trigger['recovery_mode'] == 'RECOVERY_EXPRESSION'
assert trigger['recovery_expression'] == 'last(/updates-monitor/updates.monitor.dist_upgrade.available)=0'
assert not any(t.get('value') == 'package-count' for t in trigger.get('tags', []))
print('OK: dystrybucja, brak danych ze starszego skryptu i zamykanie tylko przy potwierdzonym braku aktualizacji')
