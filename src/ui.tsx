import React,{useState,useRef,useCallback} from 'react';
import {createRoot} from 'react-dom/client';
type Contact={seq:number;phase:'down'|'move'|'up';x:number;y:number};
declare global {interface Window {deck:{record:(data:unknown)=>void;onContact:(fn:(c:Contact)=>void)=>()=>void;onLost:(fn:()=>void)=>()=>void;handled:(seq:number)=>void}}}
const role=new URLSearchParams(location.search).get('role');
function App(){
 const [count,setCount]=useState(0),[value,setValue]=useState(50),[events,setEvents]=useState<string[]>([]);
 const button=useRef<HTMLButtonElement>(null),slider=useRef<HTMLInputElement>(null),active=useRef<'button'|'slider'|null>(null);
 const record=useCallback((type:string,data:unknown={})=>{const item={time:new Date().toISOString(),role,type,data};window.deck.record(item);setEvents(old=>[JSON.stringify(item),...old].slice(0,100));},[]);
 const increment=()=>{setCount(c=>c+1);record('button',{source:'system'});};
 React.useEffect(()=>{
  const handlers=['focus','blur','keydown','keyup','pointerdown','pointerup','touchstart','touchend'].map(type=>{const fn=(e:Event)=>record(type,{trusted:e.isTrusted,key:e instanceof KeyboardEvent?e.key:undefined,pointerType:e instanceof PointerEvent?e.pointerType:undefined,x:e instanceof PointerEvent?e.clientX:undefined,y:e instanceof PointerEvent?e.clientY:undefined});window.addEventListener(type,fn);return ()=>window.removeEventListener(type,fn)});
  return ()=>handlers.forEach(fn=>fn());
 },[record]);
 React.useEffect(()=>{
  if(role!=='panel')return;
  const remove=window.deck.onContact(c=>{
   const x=c.x*innerWidth,y=c.y*innerHeight;
   const inside=(el:HTMLElement|null)=>{const r=el?.getBoundingClientRect();return !!r&&x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom;};
   if(c.phase==='down')active.current=inside(button.current)?'button':inside(slider.current)?'slider':null;
   if(active.current==='slider'&&c.phase!=='up'){
    const r=slider.current!.getBoundingClientRect();const v=Math.round(Math.max(0,Math.min(100,(x-r.left)/r.width*100)));setValue(v);record('slider',{source:'reader',value:v});
   }
   if(c.phase==='up'){
    if(active.current==='button'&&inside(button.current)){setCount(n=>n+1);record('button',{source:'reader'});}
    active.current=null;
   }
   record('contact',c);window.deck.handled(c.seq);
  });
  const lost=window.deck.onLost(()=>{active.current=null;record('reader-lost');});return ()=>{remove();lost();};
 },[record]);
 React.useEffect(()=>{const report=()=>{const rect=(el:HTMLElement|null)=>{const r=el?.getBoundingClientRect();return r&&{x:r.x,y:r.y,width:r.width,height:r.height};};record('geometry',{width:innerWidth,height:innerHeight,button:rect(button.current),slider:rect(slider.current)});};report();window.addEventListener('resize',report);return ()=>window.removeEventListener('resize',report);},[record]);
 return <main><h1>TouchDeck {role}</h1>{role==='panel'?<><button ref={button} style={{width:'95%',height:220,fontSize:48}} onClick={increment}>Счётчик {count}</button><p>Ползунок {value}</p><input ref={slider} aria-label="Ползунок" type="range" style={{width:'95%',height:70}} value={value} onChange={e=>{setValue(Number(e.target.value));record('slider',{source:'system',value:Number(e.target.value)});}}/></>:<p>Выберите это окно вручную и печатайте тестовый текст. Фокус программно не восстанавливается.</p>}<pre style={{fontSize:14,whiteSpace:'pre-wrap'}}>{events.join('\n')}</pre></main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
