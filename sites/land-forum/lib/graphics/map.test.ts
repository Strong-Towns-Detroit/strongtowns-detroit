import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { emptyFilters } from './bza.ts';
import { parseMapRecipe, mapRecipeHash, mapRecipeFromHash } from './map.ts';
test('map recipes preserve the immutable scene and filters, not a camera',()=>{
 const r={version:2,template:'map',map:'a'.repeat(64),filters:{...emptyFilters(),categories:['Parking']},title:'Cases',explanation:'Selected records',selected:'case-1'};
 assert.deepEqual(mapRecipeFromHash(mapRecipeHash(parseMapRecipe(r))),r);
 assert.throws(()=>parseMapRecipe({...r,map:'latest'}));assert.throws(()=>parseMapRecipe({...r,version:3}));
});
test('published map and release bundle agree with reviewed totals and verified hashes',async()=>{
 const root=new URL('../../public/data/',import.meta.url);
 const latest=JSON.parse(await readFile(new URL('bza-maps/latest.json',root),'utf8'));
 const raw=await readFile(new URL(`bza-maps/${latest.map}.json`,root));assert.equal(createHash('sha256').update(raw).digest('hex'),latest.map);
 const pub=JSON.parse(raw.toString()), records=await readFile(new URL(`bza-studio/${pub.bundle}.json`,root));assert.equal(createHash('sha256').update(records).digest('hex'),pub.bundle);
 const bundle=JSON.parse(records.toString());assert.equal(bundle.cases.length,417);assert.equal(bundle.cases.reduce((n:number,c:{hearings:unknown[]})=>n+c.hearings.length,0),509);
 assert.equal(pub.scene.symbols.length,408);assert.deepEqual(new Set(pub.scene.symbols.map((s:{id:string})=>s.id)),new Set(bundle.cases.filter((c:{mapped:boolean})=>c.mapped).map((c:{id:string})=>c.id)));
 assert.ok(bundle.cases.some((c:{hearings:{sourceUrl:string|null}[]})=>c.hearings.some(h=>h.sourceUrl)));
});
