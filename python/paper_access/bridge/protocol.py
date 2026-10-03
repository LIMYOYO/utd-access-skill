"""Bounded JSON framing and strict native message contracts."""
import json
import re
import struct
from uuid import UUID
from urllib.parse import urlsplit, parse_qs

LIMIT = 65536
SCHEMAS = {
    "start_ssrn": ({"request_id":str,"ssrn_id":str}, "host"),
    "ssrn_candidate": ({"request_id":str,"ssrn_id":str,"download_id":int,"path":str,"title":str,"authors":list}, "extension"),
    "start_batch": ({"request_id":str,"papers":list,"concurrency":int}, "host"),
    "batch_candidate": ({"request_id":str,"download_id":int,"path":str}, "extension"),
    "paper_failed": ({"request_id":str,"paper_id":str,"reason":str}, "extension"),
    "paper_result": ({"request_id":str,"paper_id":str,"status":str,"reason":str}, "host"),
    "seal_batch": ({"request_id":str}, "host"),
    "batch_closed": ({"request_id":str,"download_ids":list}, "extension"),
    "batch_result": ({"request_id":str,"results":list,"status":str,"reason":str}, "host"),
    "hello": ({}, "both"),
    "start_pair": ({"request_id":str,"papers":list}, "host"),
    "pool_candidate": ({"request_id":str,"download_id":int,"path":str}, "extension"),
    "seal_pair": ({"request_id":str}, "host"),
    "pool_closed": ({"request_id":str,"download_ids":list}, "extension"),
    "pair_result": ({"request_id":str,"results":list,"status":str,"reason":str}, "host"),
    "start": ({"request_id":str,"doi":str}, "host"),
    "ack": ({"request_id":str}, "extension"),
    "progress": ({"request_id":str,"phase":str}, "extension"),
    "candidate": ({"request_id":str,"download_id":int,"path":str,"title":str,"association":str}, "extension"),
    "cancel": ({"request_id":str}, "host"),
    "validation_result": ({"request_id":str,"status":str,"reason":str}, "host"),
    "error": ({"request_id":str,"reason":str}, "extension"),
}

def valid_doi(value):
    if not isinstance(value,str) or len(value)>256 or not re.fullmatch(r"10\.1287/[a-z0-9._()-]+",value,re.I):
        raise ValueError("invalid_informs_doi")
    return value.lower()

def valid_ssrn_id(value):
    if not isinstance(value,str) or len(value)>256:raise ValueError('invalid_ssrn_id')
    value=value.strip()
    if value.startswith('https://'):
        u=urlsplit(value)
        if u.username or u.password or u.port or u.fragment:raise ValueError('invalid_ssrn_url')
        if u.hostname=='doi.org':value=u.path[1:]
        elif u.hostname in ('papers.ssrn.com','ssrn.com','www.ssrn.com'):
            if u.path=='/sol3/papers.cfm':
                ids=parse_qs(u.query).get('abstract_id',[])
                value=ids[0] if len(ids)==1 else ''
            else:value=u.path.removeprefix('/abstract=') if u.path.startswith('/abstract=') else ''
        else:raise ValueError('invalid_ssrn_url')
    value=re.sub(r'^10\.2139/ssrn\.','',value,flags=re.I)
    if not re.fullmatch(r'[1-9]\d{0,9}',value):raise ValueError('invalid_ssrn_id')
    return value

def validate_message(message, direction):
    if not isinstance(message,dict) or type(message.get("v")) is not int or message["v"]!=1:
        raise ValueError("invalid_protocol_version")
    schema,source=SCHEMAS.get(message.get("type"), (None,None))
    if schema is None or source not in (direction,"both"):
        raise ValueError("invalid_message_type")
    fields={"v":int,"type":str,"session_id":str,**schema}
    if set(message)!=set(fields):raise ValueError("invalid_message_fields")
    for key,kind in fields.items():
        if type(message[key]) is not kind:raise ValueError("invalid_field_type")
        if kind is str and len(message[key])>4096:raise ValueError("field_too_long")
    for key in ("session_id","request_id","paper_id"):
        if key in message and str(UUID(message[key]))!=message[key]:raise ValueError("invalid_id")
    if "doi" in message:valid_doi(message["doi"])
    if 'ssrn_id' in message and valid_ssrn_id(message['ssrn_id'])!=message['ssrn_id']:raise ValueError('invalid_ssrn_id')
    if message['type']=='ssrn_candidate':
        authors=message['authors']
        if not message['title'].strip() or not 1<=len(authors)<=100 or any(type(a) is not str or not a.strip() or len(a)>256 for a in authors):raise ValueError('invalid_ssrn_metadata')
    if "download_id" in message and message["download_id"]<0:raise ValueError("invalid_download_id")
    if message['type'] in ('pool_closed','batch_closed'):
        ids=message['download_ids']
        if (len(ids)!=2 if message['type']=='pool_closed' else len(ids)>10) or any(type(i) is not int or i<0 for i in ids) or len(set(ids))!=len(ids):raise ValueError('invalid_pool_ids')
    if message['type'] in ('start_pair','start_batch'):
        papers=message['papers']
        if message['type']=='start_pair' and len(papers)!=2:raise ValueError('exactly_two_papers_required')
        if message['type']=='start_batch' and (not 1<=len(papers)<=10 or not 1<=message['concurrency']<=10):raise ValueError('invalid_batch_size_or_concurrency')
        for paper in papers:
            if not isinstance(paper,dict) or set(paper)!={'request_id','doi'}:raise ValueError('invalid_pair_paper')
            if str(UUID(paper['request_id']))!=paper['request_id']:raise ValueError('invalid_id')
            valid_doi(paper['doi'])
        if len({p['doi'].lower() for p in papers})!=len(papers) or len({p['request_id'] for p in papers})!=len(papers):raise ValueError('duplicate_pair_paper')
    if message['type'] in ('pair_result','batch_result'):
        if len(message['results'])>(2 if message['type']=='pair_result' else 10):raise ValueError('too_many_results')
        for result in message['results']:
            if not isinstance(result,dict) or set(result)!={'request_id','status','reason'} or not all(isinstance(v,str) and len(v)<=4096 for v in result.values()):raise ValueError('invalid_pair_result')
            if str(UUID(result['request_id']))!=result['request_id']:raise ValueError('invalid_id')
            if result['status'] not in ('verified_fulltext','downloaded_fulltext','needs_attention','failed','cancelled'):raise ValueError('invalid_result_status')
        if len({r['request_id'] for r in message['results']})!=len(message['results']):raise ValueError('duplicate_result_id')
    if 'status' in message and message['status'] not in ('verified_fulltext','downloaded_fulltext','needs_attention','failed','cancelled'):raise ValueError('invalid_result_status')
    return message

def _read_exact(stream,size):
    chunks=[]
    while size:
        block=stream.read(size)
        if not block:raise ValueError("truncated_frame")
        chunks.append(block);size-=len(block)
    return b"".join(chunks)

def read_message(stream):
    first=stream.read(1)
    if not first:return None
    size=struct.unpack("=I",first+_read_exact(stream,3))[0]
    if not 0<size<=LIMIT:raise ValueError("invalid_frame_size")
    try:value=json.loads(_read_exact(stream,size))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise ValueError("invalid_json") from exc
    if not isinstance(value,dict):raise ValueError("invalid_message")
    return value

def write_message(stream,message):
    data=json.dumps(message,ensure_ascii=False,separators=(",",":")).encode()
    if not 0<len(data)<=LIMIT:raise ValueError("invalid_frame_size")
    stream.write(struct.pack("=I",len(data))+data);stream.flush()
