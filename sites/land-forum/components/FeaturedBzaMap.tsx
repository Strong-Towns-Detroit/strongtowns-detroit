'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { renderMap } from '@strongtowns/graphics-browser';
import { loadMap } from '../lib/graphics/map';
export default function FeaturedBzaMap(){
  const [svg,setSvg]=useState(''),[coverage,setCoverage]=useState('Explore the cases behind the map.');
  useEffect(()=>{const controller=new AbortController();(async()=>{
    const response=await fetch('/data/bza-maps/latest.json',{signal:controller.signal});if(!response.ok)return;
    const latest=await response.json(),{publication,bundle}=await loadMap(latest.map,controller.signal);
    if(controller.signal.aborted)return;
    setSvg(renderMap(publication.scene,undefined,'featured'));
    setCoverage(`${bundle.cases.length} cases · ${publication.scene.symbols.length} mapped · through ${bundle.coverage.lastDate}`);
  })().catch(()=>{});return()=>controller.abort();},[]);
  return <Link href="/atlas/" className="featured-map" aria-label="Explore the Detroit BZA relief map"><div aria-hidden="true" dangerouslySetInnerHTML={{__html:svg}}/><p>{coverage}</p></Link>;
}
