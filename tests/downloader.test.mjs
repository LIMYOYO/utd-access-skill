import test from 'node:test';
import assert from 'node:assert/strict';
import { parseInformsDoi, libraryLink, matchesDownload, candidateDownload, downloadOutcome } from '../src/download-policy.js';

test('accept only complete INFORMS DOI input or publisher URL', () => {
  assert.equal(parseInformsDoi('https://pubsonline.informs.org/doi/10.1287/mnsc.2018.3061'), '10.1287/mnsc.2018.3061');
  for (const value of ['10.1000/foo', 'text 10.1287/foo', '10.1287/foo?bad', 'https://evil.test/10.1287/foo']) {
    assert.throws(() => parseInformsDoi(value));
  }
});

test('accept only observed UofT LibKey PDF links', () => {
  assert.equal(libraryLink('https://libkey.io/libraries/278/articles/123/full-text-file?utm_source=nomad'), true);
  for (const url of ['https://libkey.io.evil.test/libraries/278/articles/123/full-text-file', 'https://libkey.io/libraries/999/articles/123/full-text-file', 'javascript:alert(1)']) {
    assert.equal(libraryLink(url), false);
  }
});

const task = { phase: 'waiting_download', armedAt: 10000, viewerUrl: 'https://research.ebsco.com/c/example/viewer/pdf/abc?modal=download' };
const item = { id: 7, startTime: new Date(11000).toISOString(), referrer: 'https://research.ebsco.com/c/example/viewer/pdf/abc', mime: 'application/pdf', state: 'complete', exists: true, filename: '/tmp/paper.pdf' };
test('correlate by viewer and time, never a generic recent PDF', () => {
  assert.equal(matchesDownload(task, item), true);
  assert.equal(matchesDownload(task, {...item, referrer: ''}), false);
  assert.equal(matchesDownload(task, {...item, referrer: 'https://research.ebsco.com/c/example/viewer/pdf/other'}), false);
  assert.equal(matchesDownload(task, {...item, startTime: new Date(9000).toISOString()}), false);
  assert.equal(matchesDownload({...task, phase: 'stopped'}, item), false);
});
test('completion never means verified full text; interrupted or missing files fail', () => {
  assert.equal(downloadOutcome(item), 'downloaded_unverified');
  assert.equal(downloadOutcome({...item,state:'in_progress'}), 'waiting_download');
  assert.equal(downloadOutcome({...item,state:'interrupted'}), 'stopped');
  assert.equal(downloadOutcome({...item,exists:false}), 'stopped');
  assert.equal(downloadOutcome({...item,mime:'text/html',filename:'/tmp/login.html'}), 'stopped');
});


test('missing referrer is only an unverified EBSCO candidate within task time bounds',()=>{
  const t={...task,deadline:20000};
  const candidate={...item,referrer:'',url:'blob:https://research.ebsco.com/opaque'};
  assert.equal(candidateDownload(t,candidate),true);
  assert.equal(matchesDownload(t,candidate),false);
  for(const patch of [{url:'blob:https://evil.test/opaque'},{referrer:'https://research.ebsco.com/c/other/viewer/pdf/else'}, {startTime:new Date(20001).toISOString()}, {startTime:new Date(9999).toISOString()}]) assert.equal(candidateDownload(t,{...candidate,...patch}),false);
  assert.equal(candidateDownload({...t,phase:'stopped'},candidate),false);
});

test('accepts UofT content-location but rejects another institution',()=>{
 assert.equal(libraryLink('https://libkey.io/libraries/278/articles/368138590/content-location?utm_source=nomad'),true);
 assert.equal(libraryLink('https://libkey.io/libraries/999/articles/368138590/content-location'),false);
});
