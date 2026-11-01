const {app,BrowserWindow,ipcMain}=require('electron');
const fs=require('node:fs'),path=require('node:path'),net=require('node:net');
if(process.getuid()===0) throw Error('Run as regular user');
app.commandLine.appendSwitch('ozone-platform','wayland');
const dir=path.resolve(process.env.TOUCHDECK_RUN||'logs/current');
fs.mkdirSync(dir,{recursive:true,mode:0o700});fs.chmodSync(dir,0o700);
const log=(event,data)=>fs.appendFileSync(path.join(dir,'electron.jsonl'),JSON.stringify({time:new Date().toISOString(),event,data})+'\n');
let panel,client,pending=new Map();
const sock=path.join(dir,'reader.sock');
if(fs.existsSync(sock))throw Error('Socket exists; use a new run directory');
const server=net.createServer(s=>{
 if(client){s.destroy();return;}client=s;let buffer='',ready=false;
 s.on('data',chunk=>{
  buffer+=chunk;if(buffer.length>4096){s.destroy();return;}
  while(buffer.includes('\n')){
   const end=buffer.indexOf('\n'),line=buffer.slice(0,end);buffer=buffer.slice(end+1);
   try{
    const m=JSON.parse(line);
    if(m.type==='hello'&&m.device==='TouchDeck-Test'){ready=true;s.write('{"type":"ready"}\n');log('reader-connected');continue;}
    if(!ready||!panel||m.type!=='contact'||!Number.isSafeInteger(m.seq)||!['down','move','up'].includes(m.phase)||![m.x,m.y].every(v=>Number.isFinite(v)&&v>=0&&v<=1)||pending.size){throw Error('Invalid frame');}
    pending.set(m.seq,s);panel.webContents.send('contact',m);log('reader-frame',m);
   }catch{ s.destroy();return; }
  }
 });
 s.on('error',e=>log('reader-error',e.message));s.on('close',()=>{client=null;pending.clear();log('reader-disconnected');if(panel&&!panel.isDestroyed())panel.webContents.send('reader-lost');});
});
app.whenReady().then(()=>{
 log('launch',{argv:process.argv,wayland:process.env.WAYLAND_DISPLAY,pid:process.pid});
 for(const role of ['panel','primary']){
  const w=new BrowserWindow({title:'TouchDeck-'+role,width:900,height:700,show:false,webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
  if(role==='panel')panel=w;
  w.on('page-title-updated',e=>e.preventDefault());w.webContents.setWindowOpenHandler(()=>({action:'deny'}));w.webContents.on('will-navigate',e=>e.preventDefault());
  w.on('focus',()=>log(role+'-focus'));w.on('blur',()=>log(role+'-blur'));
  w.loadFile('src/index.html',{query:{role}});w.once('ready-to-show',()=>w.showInactive());
 }
 server.listen(sock,()=>{fs.chmodSync(sock,0o600);log('socket-ready',sock);});
});
ipcMain.on('record',(e,data)=>{if(data&&typeof data==='object'&&JSON.stringify(data).length<8000)log('renderer',data)});
ipcMain.on('handled',(e,seq)=>{if(e.sender!==panel?.webContents)return;const s=pending.get(seq);if(s&&!s.destroyed)s.write(JSON.stringify({type:'ack',seq})+'\n');pending.delete(seq);});
app.on('window-all-closed',()=>app.quit());
app.on('will-quit',()=>{client?.destroy();server.close();if(fs.existsSync(sock))fs.unlinkSync(sock);});
