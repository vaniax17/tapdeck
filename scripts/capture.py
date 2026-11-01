import subprocess,json,datetime,sys
with open(sys.argv[1],'a') as f:
 p=subprocess.Popen(['niri','msg','--json','event-stream'],stdout=subprocess.PIPE,text=True)
 try:
  for line in p.stdout:
   event=json.loads(line)
   if '--focus-only' in sys.argv and 'WindowFocusChanged' not in event:continue
   f.write(json.dumps({'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'event':event})+'\n');f.flush()
 finally:p.terminate();p.wait()
