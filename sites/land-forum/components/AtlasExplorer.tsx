'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import { renderMap } from '@strongtowns/graphics-browser';
import { emptyFilters, isBundleId, loadBundle, summarize, type BzaPublicationBundle, type BzaFilters } from '../lib/graphics/bza';
import { loadMap, mapRecipeFromHash, mapRecipeHash, type MapPublication, type MapRecipe } from '../lib/graphics/map';
import BzaMapExport from './BzaMapExport';

export default function AtlasExplorer() {
  const [publication,setPublication]=useState<MapPublication|null>(null),[bundle,setBundle]=useState<BzaPublicationBundle|null>(null);
  const [recipe,setRecipe]=useState<MapRecipe|null>(null),[error,setError]=useState(''),[attempt,setAttempt]=useState(0),[exporting,setExporting]=useState(false);
  const [camera,setCamera]=useState({zoom:1,x:0,y:0});
  const drag=useRef<{x:number;y:number;ox:number;oy:number;moved:boolean}|null>(null);
  const mapNode=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const controller=new AbortController();setError('');setPublication(null);setBundle(null);
    (async()=>{
      const saved=mapRecipeFromHash(location.hash);
      let id=saved?.map;
      if(!id){const res=await fetch('/data/bza-maps/latest.json',{signal:controller.signal});if(!res.ok)throw new Error('The atlas could not load.');const latest=await res.json();if(!isBundleId(latest.map))throw new Error('Invalid map reference.');id=latest.map;}
      setRecipe(saved??{version:2,template:'map',map:id!,filters:emptyFilters(),title:'Detroit zoning appeals',explanation:'Cases by primary relief requested. Symbol area shows hearings per case.'});
      const data=await loadMap(id!,controller.signal);
      if(controller.signal.aborted)return;
      setPublication(data.publication);setBundle(data.bundle);
      setRecipe(saved??{version:2,template:'map',map:id!,filters:emptyFilters(),title:'Detroit zoning appeals',explanation:'Cases by primary relief requested. Symbol area shows hearings per case.'});
    })().catch(async e=>{
      if(controller.signal.aborted)return;setError(e.message);
      // Source records remain usable when map loading fails. Never replace a saved view with newer data.
      if(!location.hash)try{const res=await fetch('/data/bza-studio/latest.json',{signal:controller.signal});const latest=await res.json();const cases=await loadBundle(latest.bundle,controller.signal);if(!controller.signal.aborted)setBundle(cases);}catch{}
    });return()=>controller.abort();
  },[attempt]);
  useEffect(()=>{const restore=()=>setAttempt(n=>n+1);window.addEventListener('hashchange',restore);return()=>window.removeEventListener('hashchange',restore);},[]);
  const filters=recipe?.filters??emptyFilters();
  const summary=useMemo(()=>bundle?summarize(bundle,filters):null,[bundle,filters]);
  const svg=useMemo(()=>publication&&summary?renderMap(publication.scene,summary.records.map(c=>c.id),'atlas'):null,[publication,summary]);
  const selected=bundle?.cases.find(c=>c.id===recipe?.selected);
  function update(change:Partial<MapRecipe>){if(!recipe)return;const next={...recipe,...change};setRecipe(next);history.replaceState(null,'',mapRecipeHash(next));}
  function filter(change:Partial<BzaFilters>){update({filters:{...filters,...change}});}
  function select(id:string){update({selected:id});}
  const scene=publication?.scene;
  const visibleIds=new Set(summary?.records.map(c=>c.id));
  const legend=new Map<string,{label:string;color:string;count:number}>();
  for(const symbol of scene?.symbols??[]){if(!visibleIds.has(symbol.id))continue;const item=legend.get(symbol.category)??{label:symbol.label,color:symbol.color,count:0};item.count++;legend.set(symbol.category,item);}

  const options=(key:'categoryLabel'|'outcomeLabel'|'firstDate')=>[...new Set(bundle?.cases.map(c=>key==='firstDate'?c.firstDate.slice(0,4):c[key]).filter(Boolean))].sort();
  return <section className="bza-workspace">
    {error&&<div role="alert">{error} Case records remain available when loaded. <button onClick={()=>setAttempt(n=>n+1)}>Reload map</button></div>}
    {!bundle?<p role="status">Loading recorded BZA cases…</p>:<>
    <div className="bza-filters">
      <label>Search cases<input type="search" value={filters.q} onChange={e=>filter({q:e.target.value})} placeholder="Address, petitioner, or case number" maxLength={200}/></label>
      {([['Primary request','categories','categoryLabel'],['Recorded outcome','outcomes','outcomeLabel'],['First hearing year','years','firstDate']] as const).map(([label,key,field])=><label key={key}>{label}<select aria-label={label} value={filters[key][0]??''} onChange={e=>filter({[key]:e.target.value?[e.target.value]:[]})}><option value="">All</option>{options(field).map(v=><option key={v}>{v}</option>)}</select></label>)}
      <button onClick={()=>filter(emptyFilters())}>Clear filters</button>
      <button className="primary-button" disabled={!scene||!summary?.mapped} onClick={()=>setExporting(true)}>Create graphic</button>
    </div>
    <p className="bza-counts" aria-live="polite">{summary?.total} cases · {summary?.mapped} mapped · {(summary?.total??0)-(summary?.mapped??0)} without a mapped location. Available minutes: {bundle.coverage.firstDate}–{bundle.coverage.lastDate}.</p>
    <div className="bza-layout"><div>
      <div className="map-toolbar" aria-label="Map controls"><button onClick={()=>setCamera(c=>({...c,zoom:Math.min(8,c.zoom*1.3)}))} aria-label="Zoom in">+</button><button onClick={()=>setCamera(c=>({...c,zoom:Math.max(1,c.zoom/1.3)}))} aria-label="Zoom out">−</button><button onClick={()=>setCamera({zoom:1,x:0,y:0})}>Whole Detroit</button></div>
      <div ref={mapNode} className="detroit-map" data-map-ready={!!svg} onWheel={e=>setCamera(c=>({...c,zoom:Math.max(1,Math.min(8,c.zoom*(e.deltaY<0?1.1:.9)))}))}
        onPointerDown={e=>{drag.current={x:e.clientX,y:e.clientY,ox:camera.x,oy:camera.y,moved:false};}}
        onPointerMove={e=>{const d=drag.current;if(!d||!e.buttons)return;const dx=e.clientX-d.x,dy=e.clientY-d.y;if(Math.abs(dx)+Math.abs(dy)>4)d.moved=true;if(d.moved){e.currentTarget.setPointerCapture(e.pointerId);setCamera(c=>({...c,x:d.ox+dx,y:d.oy+dy}));}}}
        onPointerUp={e=>{const moved=drag.current?.moved;drag.current=null;if(!moved){const target=(e.target as Element).closest('[data-case-id]');if(target)select(target.getAttribute('data-case-id')!);}}}
        onPointerCancel={()=>{drag.current=null;}}>
        {svg?<div className="map-artwork" style={{transform:`translate(${camera.x}px,${camera.y}px) scale(${camera.zoom})`}} dangerouslySetInnerHTML={{__html:svg}}/>:<p>The map is unavailable.</p>}
      </div>
      <p className="map-note">Color shows primary relief requested; symbol area shows hearings per case. Locations are displaced for legibility. Exports always show whole Detroit.</p>
      <ul className="map-legend">{[...legend.values()].sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label,'en')).map(c=><li key={c.label}><span style={{background:c.color}}/>{c.label} ({c.count})</li>)}</ul>
    </div><aside className="bza-records" aria-label="Case records">
      {selected&&<article className="case-detail"><button onClick={()=>update({selected:undefined})}>Close case</button><h2>{selected.address}</h2><p>{selected.caseNumber} · {selected.petitioner}</p><p>{selected.proposal}</p><p>{selected.categoryLabel} · {selected.outcomeLabel}</p>{!selected.mapped&&<p>Location not mapped.</p>}<h3>Hearing record</h3><ol>{selected.hearings.map((h,i)=><li key={i}><strong>{h.date}</strong><p>{(h as typeof h&{decision?:string}).decision}</p>{h.sourceUrl&&/^https?:\/\//.test(h.sourceUrl)?<a href={h.sourceUrl} target="_blank" rel="noreferrer">Read source minutes</a>:<span>Source link unavailable · {h.file}</span>}</li>)}</ol></article>}
      <h2>Cases ({summary?.total})</h2>{!summary?.total&&<p>No cases match these filters.</p>}
      <ul className="case-list">{summary?.records.map(c=><li key={c.id}><button aria-pressed={selected?.id===c.id} onClick={()=>select(c.id)}><strong>{c.address}</strong><span>{c.caseNumber} · {c.categoryLabel}</span>{!c.mapped&&<span>Location not mapped</span>}</button></li>)}</ul>
    </aside></div>
    </>}
    {exporting&&scene&&bundle&&recipe&&<BzaMapExport scene={scene} bundle={bundle} initial={recipe} originRect={mapNode.current?.getBoundingClientRect()} onClose={()=>setExporting(false)}/>}
  </section>;
}
