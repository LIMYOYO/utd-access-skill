"""CLI boundary for Codex; failures retain request IDs, never auto-submit twice."""
import argparse
import json
import time
import subprocess
from uuid import uuid4
from .protocol import valid_doi
from pathlib import Path
from .queue import BridgeQueue,ACTIVE
from .install import doctor,prepare_install,install_prepared,uninstall_owned,default_runtime
from ..config import data_directory


def execute(argv,data_dir=None):
    parser=argparse.ArgumentParser(prog='utd-access-skill bridge');commands=parser.add_subparsers(dest='action',required=True)
    d=commands.add_parser('doctor');d.add_argument('--json',action='store_true');d.add_argument('--runtime',type=Path)
    f=commands.add_parser('fetch');f.add_argument('doi');f.add_argument('--out',type=Path,required=True);f.add_argument('--wait-seconds',type=float,default=180)
    s=commands.add_parser('fetch-ssrn');s.add_argument('identifier');s.add_argument('--out',type=Path,required=True);s.add_argument('--wait-seconds',type=float,default=270)
    pair=commands.add_parser('experiment-pair');pair.add_argument('dois',nargs=2);pair.add_argument('--out',type=Path,required=True);pair.add_argument('--wait-seconds',type=float,default=180)
    b=commands.add_parser('fetch-batch');b.add_argument('dois',nargs='+');b.add_argument('--concurrency',type=int,default=2);b.add_argument('--out',type=Path,required=True);b.add_argument('--wait-seconds',type=float,default=1800)
    for command in (f,s,pair,b):
        command.add_argument('--version-policy',choices=['best-available','published-only'],default='best-available')
        command.add_argument('--validation-policy',choices=['advisory','strict'],default='advisory')
    for name in ('status','cancel'):
        p=commands.add_parser(name);p.add_argument('request_id')
    p=commands.add_parser('prepare');p.add_argument('--destination',type=Path,required=True);p.add_argument('--extension-id',required=True);p.add_argument('--download-root',type=Path,required=True);p.add_argument('--source-root',type=Path)
    for name in ('install','uninstall'):
        p=commands.add_parser(name);p.add_argument('--runtime',type=Path,required=True)
    args=parser.parse_args(argv);root=Path(data_dir) if data_dir else data_directory()
    try:
        if args.action=='doctor':return 0,doctor(args.runtime)
        if args.action=='prepare':return 0,prepare_install(args.destination,args.extension_id,args.download_root,args.source_root,root)
        if args.action=='install':return 0,install_prepared(args.runtime)
        if args.action=='uninstall':return 0,uninstall_owned(args.runtime)
        q=BridgeQueue(root/'bridge.sqlite3')
        if args.action=='status':return 0,q.get(args.request_id)
        if args.action=='cancel':return 0,q.cancel(args.request_id)
        if not 0<=args.wait_seconds<=3600:raise ValueError('invalid_wait_seconds')
        if not q.connected():return 2,{'status':'needs_attention','reason':'bridge_unavailable'}
        if args.action=='fetch-batch':
            dois=[valid_doi(doi) for doi in args.dois]
            if not 1<=len(dois)<=10 or not 1<=args.concurrency<=10 or len(set(dois))!=len(dois):raise ValueError('distinct_batch_dois_and_concurrency_1_to_10_required')
            papers=[{'request_id':str(uuid4()),'doi':doi,'output_dir':str((args.out/f'paper-{i+1}').expanduser().resolve()),'validation_policy':args.validation_policy,'version_policy':args.version_policy} for i,doi in enumerate(dois)]
            record=q.submit(dois[0],args.out,version_policy=args.version_policy,validation_policy=args.validation_policy,payload={'experiment':'parallel_batch','papers':papers,'concurrency':args.concurrency},ttl=max(300,((len(dois)+args.concurrency-1)//args.concurrency)*150+45))
        elif args.action=='experiment-pair':
            dois=[valid_doi(doi) for doi in args.dois]
            if len(set(dois))!=2:raise ValueError('two_distinct_dois_required')
            papers=[{'request_id':str(uuid4()),'doi':doi,'output_dir':str((args.out/f'paper-{i+1}').expanduser().resolve()),'validation_policy':args.validation_policy,'version_policy':args.version_policy} for i,doi in enumerate(dois)]
            record=q.submit(dois[0],args.out,version_policy=args.version_policy,validation_policy=args.validation_policy,payload={'experiment':'parallel_pair','papers':papers})
        elif args.action=='fetch-ssrn':record=q.submit_ssrn(args.identifier,args.out,validation_policy=args.validation_policy,version_policy=args.version_policy)
        else:record=q.submit(args.doi,args.out,validation_policy=args.validation_policy,version_policy=args.version_policy)
        rid=record['request_id'];end=time.monotonic()+args.wait_seconds
        while time.monotonic()<end:
            record=q.get(rid)
            if record['state'] not in ACTIVE:return (0 if record['state'] in ('verified_fulltext','downloaded_fulltext') else 2),record
            time.sleep(0.5)
        return 2,{'status':'pending','reason':'wait_timeout_do_not_resubmit','request_id':rid,'task':q.get(rid)}
    except subprocess.CalledProcessError as error:
        return 2,{'status':'needs_attention','reason':'runtime_preparation_failed','detail':(error.stderr or b'').decode(errors='replace')[-2000:]}
    except (OSError,ValueError,KeyError) as error:return 2,{'status':'needs_attention','reason':str(error)}


def main(argv):
    code,result=execute(argv);print(json.dumps(result,ensure_ascii=False));return code
