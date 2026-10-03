"""Copy authorized download files without following symlinks; validate locally."""
import os
import re
import stat
from pathlib import Path
from uuid import uuid4
from pypdf import PdfReader
from ..models import PaperInput, SourceRef, JobOptions
from ..institution import import_file


def stage_candidate(path,download_root,staging_dir,max_bytes=104857600):
    path=Path(path);root=Path(download_root)
    if not path.is_absolute() or not root.is_absolute() or '..' in path.parts or '..' in root.parts:
        raise ValueError('unsafe_candidate_path')
    try:relative=path.relative_to(root)
    except ValueError as exc:raise ValueError('candidate_outside_download_root') from exc
    if not relative.parts or path.suffix.lower()!='.pdf':raise ValueError('candidate_not_pdf')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    dest=None
    try:
        for part in path.parts[1:-1]:
            nextfd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=nextfd
        filefd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        with os.fdopen(filefd,'rb') as source:
            before=os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=max_bytes:raise ValueError('invalid_candidate_size_or_type')
            if source.read(5)!=b'%PDF-':raise ValueError('candidate_not_pdf')
            source.seek(0);Path(staging_dir).mkdir(parents=True,exist_ok=True,mode=0o700)
            dest=Path(staging_dir)/(str(uuid4())+'.pdf')
            outfd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(outfd,'wb') as target:
                total=0
                while block:=source.read(65536):
                    total+=len(block)
                    if total>max_bytes:raise ValueError('candidate_too_large')
                    target.write(block)
            after=os.fstat(source.fileno())
            if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns) or total!=before.st_size:
                raise ValueError('candidate_changed')
        return dest
    except (OSError,ValueError):
        if dest:dest.unlink(missing_ok=True)
        raise ValueError('unsafe_or_changed_candidate')
    finally:os.close(fd)


def published_informs_evidence(pdf,doi):
    try:
        reader=PdfReader(pdf);text='\n'.join(page.extract_text() or '' for page in reader.pages[:2])
    except Exception:return None
    front=text[:14000]
    if re.search(r"accepted\s+manuscript|preprint|working\s+paper|author.?s?\s+accepted",front,re.I):return None
    if doi.lower() not in front.lower() or not re.search(r'INFORMS',front):return None
    if not re.search(r'Vol\.\s*\d+|Published Online|Articles in Advance',front,re.I):return None
    if not re.search(r'MANAGEMENT SCIENCE|OPERATIONS RESEARCH|MANUFACTURING\s*&?\s*SERVICE OPERATIONS MANAGEMENT',front,re.I):return None
    return 'PDF identity pages contain INFORMS journal, publication markers and requested DOI; no manuscript-version conflict'


def validate_candidate(request,candidate,config,store):
    staged=stage_candidate(candidate['path'],Path(config['download_root']),Path(config['data_dir'])/'bridge-staging')
    try:
        evidence=published_informs_evidence(staged,request['doi'])
        paper=PaperInput('doi',request['doi'],(SourceRef('native-bridge',1,request['doi']),),candidate.get('title',''))
        job=store.create([paper],[],JobOptions(Path(request['output_dir']),version_policy=request.get('version_policy','best-available'),validation_policy=request.get('validation_policy','advisory')))
        code=import_file(job,paper.paper_id,staged,store,version='publishedVersion' if evidence else 'unknown',version_evidence=evidence or 'Browser download; publication version not established')
        from .delivery import delivery_result
        return {**delivery_result(job,store),'version_evidence':evidence or 'Publication version unknown','source':'native-bridge'}
    finally:staged.unlink(missing_ok=True)
