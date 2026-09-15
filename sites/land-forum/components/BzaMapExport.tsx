'use client';
import { useEffect, useRef, useState } from 'react';
import { embeddedFontCss, pngBlob, renderMapGraphic, type GraphicPage, type MapScene } from '@strongtowns/graphics-browser';
import { summarize, type BzaPublicationBundle } from '../lib/graphics/bza';
import { mapRecipeHash, type MapRecipe } from '../lib/graphics/map';

export default function BzaMapExport({ scene, bundle, initial, originRect, onClose }: { scene: MapScene; bundle: BzaPublicationBundle; initial: MapRecipe; originRect?: DOMRect; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const animated = useRef(false);
  const [recipe,setRecipe] = useState(initial), [page,setPage] = useState<GraphicPage|null>(null);
  const [error,setError] = useState(''), [attempt,setAttempt] = useState(0), [busy,setBusy] = useState(false), [copied,setCopied] = useState(false);
  useEffect(()=>{ const previous=document.activeElement as HTMLElement; dialog.current?.showModal(); return ()=>previous?.focus(); },[]);
  useEffect(()=>{
    let cancelled=false; setPage(null); setError('');
    (async()=>{
      const fontCss=await embeddedFontCss(['/fonts/inter-latin.woff2']);
      await document.fonts.ready;
      const canvas=document.createElement('canvas'), ctx=canvas.getContext('2d');
      if(!ctx) throw new Error('Preview rendering is unavailable.');
      const summary=summarize(bundle,recipe.filters);
      const notes=`${summary.total} cases; ${summary.mapped} mapped. Detroit BZA minutes, ${bundle.coverage.firstDate}–${bundle.coverage.lastDate}. Locations displaced; coverage incomplete.`;
      const rendered=renderMapGraphic({scene,ids:summary.records.map(c=>c.id),title:recipe.title,explanation:recipe.explanation,notes,brand:'LAND FORUM',attribution:'A project of Strong Towns Detroit'}, {fontCss,measure:(text,size)=>{ctx.font=`${size===48?700:400} ${size}px Inter`;return ctx.measureText(text).width;}});
      if(!cancelled)setPage(rendered);
    })().catch(e=>{if(!cancelled)setError(e.message);});
    return ()=>{cancelled=true;};
  },[recipe,scene,bundle,attempt]);
  useEffect(()=>{
    if(!page||animated.current)return;animated.current=true;
    if(!originRect||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
    const map=dialog.current?.querySelector<SVGSVGElement>('.export-preview svg svg');
    if(!map)return;
    const target=map.getBoundingClientRect(), scale=target.width/map.viewBox.baseVal.width;
    map.style.transformOrigin='0 0';
    map.animate([{transform:`translate(${(originRect.x-target.x)/scale}px, ${(originRect.y-target.y)/scale}px) scale(${originRect.width/target.width})`},{transform:'none'}],{duration:500,easing:'cubic-bezier(.2,.8,.2,1)'});
  },[page,originRect]);
  async function download(){if(!page)return;setBusy(true);setError('');try{const blob=await pngBlob(page),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`land-forum-bza-${recipe.map.slice(0,12)}.png`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function share(){try{await navigator.clipboard.writeText(`${location.origin}/atlas/${mapRecipeHash(recipe)}`);setCopied(true);}catch{setError('Copy is unavailable. Download the settings to preserve this graphic.');}}
  function settings(){const url=URL.createObjectURL(new Blob([JSON.stringify(recipe,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='land-forum-map.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  return <dialog ref={dialog} className="map-export" aria-labelledby="export-title" onCancel={onClose}>
    <div className="export-controls"><button onClick={onClose} autoFocus aria-label="Close graphic preview">Close</button><h2 id="export-title">Create graphic</h2><p>Whole Detroit, with your selected cases. Exploring at a different zoom does not crop the published map.</p>
      <label>Headline<input maxLength={160} value={recipe.title} onChange={e=>setRecipe({...recipe,title:e.target.value})}/></label>
      <label>Explanation<textarea maxLength={240} value={recipe.explanation} onChange={e=>setRecipe({...recipe,explanation:e.target.value})}/></label>
      <button disabled={!page||busy} onClick={download}>{busy?'Preparing PNG…':'Download Instagram PNG'}</button>
      <button onClick={share} disabled={!page}>{copied?'Link copied':'Copy graphic link'}</button><button onClick={settings} disabled={!page}>Save settings</button>
      {error&&<div role="alert">{error}<button onClick={()=>setAttempt(n=>n+1)}>Retry preview</button></div>}
    </div><div className="export-preview">{page?<div aria-label={page.altText} dangerouslySetInnerHTML={{__html:page.svg}}/>:<p role="status">Preparing your graphic…</p>}</div>
  </dialog>;
}
