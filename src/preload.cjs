const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('deck',{
 record:data=>ipcRenderer.send('record',data),
 onContact:fn=>{const cb=(_,data)=>fn(data);ipcRenderer.on('contact',cb);return ()=>ipcRenderer.removeListener('contact',cb);},
 onLost:fn=>{const cb=()=>fn();ipcRenderer.on('reader-lost',cb);return ()=>ipcRenderer.removeListener('reader-lost',cb);},
 handled:seq=>ipcRenderer.send('handled',seq)
});
