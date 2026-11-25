from pathlib import Path
import os,subprocess,tempfile
root=Path(__file__).resolve().parents[2]
doc=(root/'README.md').read_text()
block=doc.split('```sh\n',1)[1].split('```',1)[0]
assert len(block.strip().splitlines()) == 3 and block.count('&&') == 2
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);bin=p/'bin';bin.mkdir()
 scripts={
 'gh': '#!/bin/sh\nif [ "$1" = auth ]; then exit 0; fi\ncase "$TEST_MODE" in\nfailed) printf "Not Found"; exit 1;;\nhtml) printf "<html>Not Found</html>";;\ntruncated) printf "!<ar";;\nvalid) cat "$TEST_DEB";;\nesac\n',
 'dpkg-deb': '#!/bin/sh\nexit 0\n',
 'sudo': '#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_INSTALL_LOG"\n'
 }
 for name,s in scripts.items(): (bin/name).write_text(s);(bin/name).chmod(0o755)
 env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],TEST_DEB=str(root/'install/updates-monitor_0.5.17-2_all.deb'),TEST_INSTALL_LOG=str(p/'install.log'))
 for mode in ['failed','html','truncated','valid']:
  dest=p/'updates-monitor.deb';dest.write_text('previous file')
  log=p/'install.log';log.write_text('');env['TEST_MODE']=mode
  r=subprocess.run(['bash','-c',block],cwd=p,env=env,capture_output=True,text=True)
  if mode=='valid':assert r.returncode==0 and dest.read_bytes()==Path(env['TEST_DEB']).read_bytes() and log.read_text(),r
  else:assert r.returncode!=0 and not log.read_text(),(mode,r)
  assert not list(p.glob('updates-monitor-download.*'))
  print('DOWNLOAD_PROCEDURE_VERIFIED',mode)
