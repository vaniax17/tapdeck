#!/usr/bin/env python
"""Bounded uinput experiment. B's reader is a separate process; only its own device is grabbed."""
from contextlib import closing
import argparse,datetime,json,multiprocessing as mp,os,pathlib,select,signal,socket,subprocess,time,uuid
from evdev import UInput,InputDevice,AbsInfo,ecodes as E

def log(path,**kw):
 line=json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw));print(line,flush=True)
 with open(path,'a') as f:f.write(line+'\n')

def read_json(stream):
 line=stream.readline(4097)
 if not line or len(line)>4096:raise RuntimeError('IPC disconnected/oversized')
 return json.loads(line)

def reader(node,phys,sock,pipe,logfile):
 try:
  with closing(InputDevice(node)) as dev:
   if dev.name!='TouchDeck-Test' or dev.phys!=phys or dev.info.vendor!=0x1209 or dev.info.product!=0x5444 or E.INPUT_PROP_DIRECT not in dev.input_props():raise RuntimeError('Wrong device')
   dev.grab()
   log(logfile,event='reader-grabbed',node=node,pid=os.getpid(),phys=phys)
   with socket.socket(socket.AF_UNIX) as s:
    s.settimeout(1);s.connect(sock);stream=s.makefile('rwb',buffering=0)
    stream.write(b'{"type":"hello","device":"TouchDeck-Test"}\n')
    if read_json(stream)!={'type':'ready'}:raise RuntimeError('No IPC ready')
    pipe.send('ready');seq=0;tracking=-1;was=False;x=y=0
    while True:
     if pipe.poll():
      if pipe.recv()=='stop':return
     if not select.select([dev.fd],[],[],.1)[0]:continue
     for ev in dev.read():
      if ev.type==E.EV_ABS:
       if ev.code==E.ABS_MT_TRACKING_ID:tracking=ev.value
       elif ev.code==E.ABS_MT_POSITION_X:x=ev.value
       elif ev.code==E.ABS_MT_POSITION_Y:y=ev.value
      elif ev.type==E.EV_SYN:
       if ev.code==E.SYN_DROPPED:raise RuntimeError('SYN_DROPPED')
       if ev.code!=E.SYN_REPORT:continue
       now=tracking>=0
       if not now and not was:continue
       seq+=1;frame=dict(type='contact',seq=seq,phase='down' if now and not was else 'move' if now else 'up',x=x/32767,y=y/32767)
       stream.write((json.dumps(frame)+'\n').encode());ack=read_json(stream)
       if ack!={'type':'ack','seq':seq}:raise RuntimeError('No renderer ACK')
       log(logfile,event='reader-delivered',**frame);pipe.send('frame');was=now
 except BaseException as e:
  log(logfile,event='reader-stopped',error=str(e))
  try:pipe.send('error')
  except (BrokenPipeError,EOFError):pass
 finally:pipe.close()

def focused():
 w=json.loads(subprocess.check_output(['niri','msg','--json','focused-window']))
 return {k:w[k] for k in ['id','app_id','is_focused']} if w else None

def primary(app_id=None):
 w=json.loads(subprocess.check_output(['niri','msg','--json','focused-window']))
 return bool(w and (w['app_id']==app_id if app_id else w['title']=='TouchDeck-primary'))

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['A','B'],default='A');p.add_argument('--x',type=int,required=True);p.add_argument('--y',type=int,required=True);p.add_argument('--move-x',type=int);p.add_argument('--confirmed-hit',action='store_true');p.add_argument('--arm-on-primary',action='store_true');p.add_argument('--socket');p.add_argument('--log',default='logs/generator.jsonl');p.add_argument('--arm-app-id');p.add_argument('--taps',type=int,default=1);a=p.parse_args()
 if not 1<=a.taps<=5:p.error('taps must be 1..5')
 if a.taps>1 and (a.mode!='B' or not a.confirmed_hit or a.move_x is not None):p.error('Series needs B, confirmed hit, and no movement')
 armed=a.arm_on_primary or bool(a.arm_app_id)
 if os.getuid()==0:p.error('Run as regular user')
 if not(0<=a.x<=32767 and 0<=a.y<=32767):p.error('Coordinates must be 0..32767')
 if a.move_x is not None and not(a.confirmed_hit and 0<=a.move_x<=32767):p.error('Movement requires confirmed first hit and valid coordinate')
 if a.mode=='B' and not a.socket:p.error('B needs --socket')
 pathlib.Path(a.log).parent.mkdir(parents=True,exist_ok=True)
 def stop(*_):raise KeyboardInterrupt
 signal.signal(signal.SIGTERM,stop)
 axis=lambda maximum:AbsInfo(0,0,maximum,0,0,0)
 caps={E.EV_KEY:[E.BTN_TOUCH],E.EV_ABS:[(E.ABS_X,axis(32767)),(E.ABS_Y,axis(32767)),(E.ABS_MT_SLOT,axis(1)),(E.ABS_MT_TRACKING_ID,AbsInfo(-1,0,65535,0,0,0)),(E.ABS_MT_POSITION_X,axis(32767)),(E.ABS_MT_POSITION_Y,axis(32767))]}
 proc=None;conn=None;phys='touchdeck/'+uuid.uuid4().hex
 with UInput(caps,name='TouchDeck-Test',vendor=0x1209,product=0x5444,phys=phys,input_props=[E.INPUT_PROP_DIRECT]) as ui:
  try:
   node=ui.device.path;log(a.log,event='created',mode=a.mode,node=node,phys=phys)
   subprocess.run(['udevadm','settle','--timeout=5'],check=True)
   props=subprocess.check_output(['udevadm','info','-q','property','-n',node],text=True)
   log(a.log,event='udev',properties=props)
   if 'ID_INPUT_TOUCHSCREEN=1' not in props or any(v in props for v in ['ID_INPUT_MOUSE=1','ID_INPUT_TOUCHPAD=1']):raise RuntimeError('Classification failed')
   subprocess.run([str(pathlib.Path(__file__).resolve().parent/'probe'),node],check=True)
   if a.mode=='B':
    conn,child=mp.Pipe();proc=mp.Process(target=reader,args=(node,phys,a.socket,child,a.log));proc.start();child.close()
    if not conn.poll(5) or conn.recv()!='ready':raise RuntimeError('No reader grab+IPC confirmation')
    log(a.log,event='reader-ready')
   def healthy():
    if proc and (not proc.is_alive() or conn.poll()):raise RuntimeError('Reader lost; stop generation')
   def pause(seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:healthy();time.sleep(min(.02,max(0,until-time.monotonic())))
   deadline=time.monotonic()+180;stable=0
   if armed:
    while stable<3:
     if time.monotonic()>deadline:raise RuntimeError('Focus wait timeout')
     stable=stable+1 if primary(a.arm_app_id) else 0;pause(1)
   else:
    print('Enter: countdown; Ctrl-C: emergency stop (timeout 180s)',flush=True)
    while not select.select([0],[],[],.1)[0]:
     healthy()
     if time.monotonic()>deadline:raise RuntimeError('Arm timeout')
    if not input()=='':raise RuntimeError('Cancelled')
   for n in range(3,0,-1):
    if armed and not primary(a.arm_app_id):raise RuntimeError('Initial focus lost; abort')
    log(a.log,event='countdown',remaining=n);pause(1)
   if armed and not primary(a.arm_app_id):raise RuntimeError('Initial focus lost; abort')
   log(a.log,event='test-start',focused=focused())
   def frame(phase,x):
    healthy()
    ui.write(E.EV_ABS,E.ABS_MT_SLOT,0)
    if phase=='down':ui.write(E.EV_ABS,E.ABS_MT_TRACKING_ID,1)
    if phase=='up':ui.write(E.EV_ABS,E.ABS_MT_TRACKING_ID,-1)
    else:
     for code,v in [(E.ABS_X,x),(E.ABS_Y,a.y),(E.ABS_MT_POSITION_X,x),(E.ABS_MT_POSITION_Y,a.y)]:ui.write(E.EV_ABS,code,v)
    ui.write(E.EV_KEY,E.BTN_TOUCH,0 if phase=='up' else 1);ui.syn();log(a.log,event='sent',phase=phase,x=x,y=a.y)
    if conn and (not conn.poll(2) or conn.recv()!='frame'):raise RuntimeError('Reader/renderer frame ACK lost')
   for tap in range(a.taps):
    if armed and not primary(a.arm_app_id):raise RuntimeError('Focus lost before tap; abort')
    log(a.log,event='tap',number=tap+1,total=a.taps)
    frame('down',a.x);pause(.15)
    if a.move_x is not None:
     for i in range(1,21):frame('move',round(a.x+(a.move_x-a.x)*i/20));pause(.02)
    frame('up',a.move_x if a.move_x is not None else a.x);pause(2)
   log(a.log,event='test-end',focused=focused())
  finally:
   # On reader failure close uinput without injecting an ungrabbed release.
   if proc:
    if proc.is_alive():
     try:conn.send('stop')
     except (BrokenPipeError,EOFError):pass
     proc.join(1)
    if proc.is_alive():proc.terminate();proc.join(1)
    conn.close()
   log(a.log,event='destroying',node=ui.device.path)
 log(a.log,event='destroyed')
if __name__=='__main__':
 try:main()
 except KeyboardInterrupt:print('Stopped',flush=True)
