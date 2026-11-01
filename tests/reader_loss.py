"""Integration safety check: kill only our reader before countdown/events."""
import json,os,pathlib,signal,subprocess,sys,time
root=pathlib.Path(__file__).resolve().parents[1]
log=root/'logs/B/reader-loss.jsonl'
if log.exists():raise SystemExit('Use a fresh reader-loss log')
p=subprocess.Popen([sys.executable,str(root/'scripts/touch.py'),'--mode','B','--socket',str(root/'logs/B/reader.sock'),'--x','16384','--y','6000','--log',str(log)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
try:
 deadline=time.monotonic()+8
 while time.monotonic()<deadline:
  rows=[json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
  ready=next((r for r in rows if r['event']=='reader-ready'),None)
  if ready:break
  time.sleep(.05)
 assert ready,'Reader did not become ready'
 reader=next(r for r in rows if r['event']=='reader-grabbed')
 os.kill(reader['pid'],signal.SIGKILL)
 p.communicate(timeout=4)
 rows=[json.loads(l) for l in log.read_text().splitlines()]
 assert p.returncode!=0,'Generator should fail closed'
 assert not any(r['event']=='sent' for r in rows),'Unexpected event after reader loss'
 node=next(r['node'] for r in rows if r['event']=='created')
 assert not pathlib.Path(node).exists(),'Device leaked'
 print('PASS: reader loss stopped generator, zero events, device removed')
finally:
 if p.poll() is None:p.terminate();p.wait(timeout=3)
