#!/usr/bin/env python3
"""Version order, both mismatch directions, old agents, release errors and bundle consistency."""
import json
from pathlib import Path
import re
import subprocess
ROOT = Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION').read_text().strip()
d=json.loads((ROOT/'zabbix-updates-monitor.json').read_text())['zabbix_export']
t=d['templates'][0];items={i['key']:i for i in t['items']};macros={m['macro']:m['value'] for m in t['macros']}
harness='var f=new Function("value",process.argv[1]); try { console.log(JSON.stringify(f(process.argv[2]))); } catch(e) { console.log("ERROR"); }'
def run(key,payload):
    js=items[key]['preprocessing'][0]['parameters'][0]
    return subprocess.check_output(['node','-e',harness,js,json.dumps(payload)],text=True).strip()
def code(v):
    return int(run('updates.monitor.version_code',{'monitor_version':v}))
assert code('0.5.10-1')>code('0.5.9-9')
assert code('0.5.17-2')>code('0.5.17-1')
assert code('1.0.0-0')>code('0.999.999-999')
assert run('updates.monitor.version_code',{'valid':0,'monitor_version':version})==str(code(version))
assert run('updates.monitor.version_code',{})=='0'
assert run('updates.monitor.version_code',{'monitor_version':'garbage'})=='0'
assert run('updates.monitor.version',{})=='"niezgłoszona"'
assert run('updates.monitor.latest.version_code',{'tag_name':'v'+version,'draft':False,'prerelease':False})==str(code(version))
for payload in [{'tag_name':'invalid'}, {'tag_name':'v'+version,'prerelease':True}, {'message':'Not Found'}, {'tag_name':'v'+version,'draft':True}]:
    assert run('updates.monitor.latest.version_code',payload)=='ERROR',payload
assert t['vendor']['version']==version
assert macros['{$UPDATES.MONITOR.VERSION}']==version
assert int(macros['{$UPDATES.MONITOR.VERSION.CODE}'])==code(version)
assert int(macros['{$UPDATES.MONITOR.REQUIRED.VERSION.CODE}'])==code(version)
assert macros['{$UPDATES.MONITOR.GITHUB.CHECK}']=='0'
assert macros['{$UPDATES.MONITOR.GITHUB.TOKEN}']==''
for file in ['updates-monitor.py','redhat/check.py']:
    text=(ROOT/file).read_text()
    assert re.search(r"^VERSION = ['\"]"+re.escape(version)+r"['\"]$",text,re.M),file
    assert "result['monitor_version'] = VERSION" in text,file
assert "version='"+version+"'" in (ROOT/'updates-monitor').read_text()
assert 'Version: '+version in (ROOT/'debian/control').read_text()
assert 'updates-monitor_'+version+'_all.deb' in (ROOT/'build-deb.py').read_text()
trigger=next(x for x in d['triggers'] if x['name']=='Niezgodne lub nieaktualne wersje updates-monitor')
expr=trigger['expression']
assert 'updates.monitor.version_code)<>{$UPDATES.MONITOR.VERSION.CODE}' in expr
assert 'updates.monitor.version_code)<{$UPDATES.MONITOR.REQUIRED.VERSION.CODE}' in expr
assert '{$UPDATES.MONITOR.VERSION.CODE}<{$UPDATES.MONITOR.REQUIRED.VERSION.CODE}' in expr
latest_expr=next(x['expression'] for x in d['triggers'] if x['name']=='Nowsze wydanie updates-monitor niż skrypt lub szablon')
assert 'updates.monitor.version_code)<last(/updates-monitor/updates.monitor.latest.version_code)' in latest_expr
assert '{$UPDATES.MONITOR.VERSION.CODE}<last(/updates-monitor/updates.monitor.latest.version_code)' in latest_expr
assert 'latest.' not in expr
assert all(x['status']=='DISABLED' for x in d['triggers'] if x['name'] in ['Nowsze wydanie updates-monitor niż skrypt lub szablon','Brak aktualnych danych o najnowszej wersji updates-monitor'])
# Evaluate the actual exported numeric expression, with no remote version needed when disabled.
def alarm(agent,template,required,enabled=False,latest=0):
    numeric=expr.replace('last(/updates-monitor/updates.monitor.version)<>""','1')
    if enabled: numeric='('+numeric+') or ('+latest_expr.replace('last(/updates-monitor/updates.monitor.latest.version)<>""','1')+')'
    for token,value in [('last(/updates-monitor/updates.monitor.version_code)',agent),('last(/updates-monitor/updates.monitor.latest.version_code)',latest),('{$UPDATES.MONITOR.VERSION.CODE}',template),('{$UPDATES.MONITOR.REQUIRED.VERSION.CODE}',required),('{$UPDATES.MONITOR.GITHUB.CHECK}',int(enabled))]:
        numeric=numeric.replace(token,str(value))
    numeric=numeric.replace('<>','!=').replace('=1','==1')
    return bool(eval(numeric,{'__builtins__':{}},{}))
old=code('0.5.16-1');new=code(version);future=code('0.5.18-1')
assert not alarm(new,new,new)
assert alarm(old,new,new)
assert alarm(new,old,new)
assert alarm(old,old,new)
assert alarm(old,old,old,True,new)
assert not alarm(new,new,new,True,old)
assert not alarm(future,future,new,True,new)
assert alarm(0,new,new)
http=items['updates.monitor.latest.raw']
assert http['status']=='DISABLED' and http['verify_peer']=='YES' and http['verify_host']=='YES'
assert http['delay']=='1h'
print('OK: version header, numeric revision order, both mismatch directions, minimum version and optional GitHub')
