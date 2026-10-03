import test from 'node:test';
import assert from 'node:assert/strict';
import { inspectOrAct } from '../src/download-page.js';

function inspect(metadata, suppliedLink) {
  const original = globalThis.document;
  const link = suppliedLink || {textContent:'Download PDFUniversity of Toronto',href:'https://libkey.io/libraries/278/articles/278769548/full-text-file?utm_source=nomad',getAttribute:()=>null};
  globalThis.document = {
    querySelectorAll: selector => selector === 'meta' ? metadata.map(([name,content])=>({getAttribute:key=>key==='name'?name:content})) : selector === 'a[href]' ? [link] : [],
    querySelector: () => ({textContent:'Cournot Competition in Networked Markets'})
  };
  try {return inspectOrAct('publisher',{doi:'10.1287/mnsc.2018.3061'});}
  finally {if(original===undefined)delete globalThis.document;else globalThis.document=original;}
}
test('supports actual INFORMS publication_doi and mixed-case Dublin Core metadata',()=>{
  const result=inspect([['dc.Title','Cournot Competition in Networked Markets'],['dc.Identifier','mnsc.2018.3061'],['dc.Identifier','10.1287/mnsc.2018.3061'],['publication_doi','10.1287/mnsc.2018.3061']]);
  assert.equal(result.title,'Cournot Competition in Networked Markets');assert.match(result.href,/libraries\/278/);
});
test('conflicting DOI metadata stops instead of accepting a matching title',()=>{
  assert.ok(inspect([['publication_doi','10.1287/mnsc.2018.3061'],['citation_doi','10.1287/other']]).error);
});
test('missing full DOI metadata waits instead of guessing',()=>{
  assert.equal(inspect([['dc.Identifier','mnsc.2018.3061']]).waiting,true);
});

test('accepts the observed UofT Article Link entry',()=>{
 const link={textContent:'Article Link University of Toronto',href:'https://libkey.io/libraries/278/articles/368138590/content-location?utm_source=nomad',getAttribute:()=>null};
 assert.equal(inspect([['publication_doi','10.1287/mnsc.2018.3061']],link).href,link.href);
});
function details(title,href) {
 const oldDocument=globalThis.document,oldLocation=globalThis.location;
 globalThis.location={origin:'https://research.ebsco.com',pathname:'/c/gsemyh/search/details/dcxkuutxpf'};
 const link={textContent:'转到全功能阅读视图。',href,getAttribute:()=>null};
 globalThis.document={querySelectorAll:s=>s==='a[href]'?[link]:[],querySelector:()=>({textContent:title})};
 try{return inspectOrAct('viewer',{doi:'10.1287/msom.2019.0800',title:'Grocery Store Density and Food Waste'});}
 finally{globalThis.document=oldDocument;globalThis.location=oldLocation;}
}
test('details page offers the observed same-record PDF viewer',()=>{
 assert.equal(details('Grocery Store Density and Food Waste.','https://research.ebsco.com/c/gsemyh/viewer/pdf/dcxkuutxpf').navigate,'https://research.ebsco.com/c/gsemyh/viewer/pdf/dcxkuutxpf');
});
test('details route refuses mismatched title, foreign or different-record viewer',()=>{
 assert.ok(details('Different paper','https://research.ebsco.com/c/gsemyh/viewer/pdf/dcxkuutxpf').error);
 for(const href of ['https://example.org/c/gsemyh/viewer/pdf/dcxkuutxpf','https://research.ebsco.com/c/gsemyh/viewer/pdf/other'])assert.equal(details('Grocery Store Density and Food Waste.',href).waiting,true);
});
