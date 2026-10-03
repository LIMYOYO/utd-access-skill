"""Transactional single-flight queue, separate from article validation records."""
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from .protocol import valid_doi, valid_ssrn_id

ACTIVE=("queued","dispatched","downloading","downloaded_unverified","verifying")
STATES=ACTIVE+("verified_fulltext","downloaded_fulltext","needs_attention","failed","cancelled")

class BridgeQueue:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.is_symlink():raise ValueError("unsafe_queue_path")
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, doi TEXT NOT NULL, output_dir TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL, session_id TEXT, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS connection (singleton INTEGER PRIMARY KEY CHECK(singleton=1), session_id TEXT, heartbeat REAL)")
            columns={row[1] for row in db.execute('PRAGMA table_info(requests)')}
            if 'validation_policy' not in columns:
                db.execute("ALTER TABLE requests ADD COLUMN validation_policy TEXT NOT NULL DEFAULT 'strict'")
            if 'version_policy' not in columns:
                db.execute("ALTER TABLE requests ADD COLUMN version_policy TEXT NOT NULL DEFAULT 'best-available'")
        os.chmod(self.path,0o600)
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE");yield db;db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()
    @staticmethod
    def decode(row):
        if row is None:raise ValueError("unknown_request")
        result=dict(row);result['payload']=json.loads(result['payload']);return result
    def submit(self,doi,output_dir,now=None,*,payload=None,ttl=300,validation_policy="advisory",version_policy="best-available"):
        return self._submit(valid_doi(doi),output_dir,now,payload=payload,ttl=ttl,validation_policy=validation_policy,version_policy=version_policy)
    def submit_ssrn(self,identifier,output_dir,now=None,*,ttl=300,validation_policy="advisory",version_policy="best-available"):
        return self._submit('10.2139/ssrn.'+valid_ssrn_id(identifier),output_dir,now,ttl=ttl,validation_policy=validation_policy,version_policy=version_policy)
    def _submit(self,doi,output_dir,now=None,*,payload=None,ttl=300,validation_policy="advisory",version_policy="best-available"):
        if version_policy not in {"best-available","published-only"}:raise ValueError("invalid_version_policy")
        if validation_policy not in {"advisory","strict"}:raise ValueError("invalid_validation_policy")
        if not isinstance(ttl,(int,float)) or isinstance(ttl,bool) or not 0<ttl<=3600:raise ValueError("invalid_request_ttl")
        now=time.time() if now is None else now
        rid=str(uuid4())
        with self.db() as db:
            db.execute("UPDATE requests SET state='failed',payload=? WHERE state='queued' AND expires<?",(json.dumps({'reason':'expired'}),now))
            if db.execute("SELECT 1 FROM requests WHERE state IN (?,?,?,?,?)",ACTIVE).fetchone():raise ValueError("bridge_busy")
            db.execute("INSERT INTO requests(request_id,doi,output_dir,created,expires,state,session_id,payload,validation_policy,version_policy) VALUES(?,?,?,?,?,'queued',NULL,?,?,?)",(rid,doi,str(Path(output_dir).expanduser().resolve()),now,now+ttl,json.dumps(payload or {}),validation_policy,version_policy))
        return self.get(rid)
    def get(self,rid):
        with self.db() as db:return self.decode(db.execute("SELECT * FROM requests WHERE request_id=?",(rid,)).fetchone())
    def claim(self,session_id,now=None):
        now=time.time() if now is None else now
        with self.db() as db:
            db.execute("UPDATE requests SET state='failed',payload=? WHERE state='queued' AND expires<?",(json.dumps({'reason':'expired'}),now))
            row=db.execute("SELECT * FROM requests WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
            if row is None:return None
            db.execute("UPDATE requests SET state='dispatched',session_id=? WHERE request_id=? AND state='queued'",(session_id,row['request_id']))
            rid=row['request_id']
        return self.get(rid)
    def transition(self,rid,session_id,expected,state,payload):
        if state not in STATES or not expected:raise ValueError("invalid_state")
        with self.db() as db:
            placeholders=','.join('?' for _ in expected)
            return db.execute(f"UPDATE requests SET state=?,payload=? WHERE request_id=? AND session_id=? AND state IN ({placeholders})",(state,json.dumps(payload),rid,session_id,*expected)).rowcount==1
    def cancel(self,rid):
        with self.db() as db:
            db.execute("UPDATE requests SET state='cancelled' WHERE request_id=? AND state IN (?,?,?,?,?)",(rid,*ACTIVE))
        return self.get(rid)
    def disconnect(self,session_id):
        with self.db() as db:
            db.execute("UPDATE requests SET state='needs_attention',payload=? WHERE session_id=? AND state IN ('dispatched','downloading')",(json.dumps({'reason':'bridge_disconnected_no_replay'}),session_id))
            db.execute("DELETE FROM connection WHERE session_id=?",(session_id,))
    def connect(self,session_id):
        now=time.time()
        with self.db() as db:
            row=db.execute("SELECT * FROM connection WHERE singleton=1").fetchone()
            if row and row['session_id']!=session_id and row['heartbeat']>now-10:raise ValueError("another_bridge_connected")
            # A dead owner never causes a browser action to be dispatched again.
            db.execute("UPDATE requests SET state='needs_attention' WHERE state IN ('dispatched','downloading') AND session_id!=?",(session_id,))
            db.execute("UPDATE requests SET state='downloaded_unverified' WHERE state='verifying' AND session_id!=?",(session_id,))
            db.execute("INSERT OR REPLACE INTO connection VALUES(1,?,?)",(session_id,now))
    def heartbeat(self,session_id):
        with self.db() as db:
            return db.execute("UPDATE connection SET heartbeat=? WHERE session_id=?",(time.time(),session_id)).rowcount==1
    def connected(self):
        with self.db() as db:
            row=db.execute("SELECT * FROM connection WHERE singleton=1").fetchone()
        return bool(row and row['heartbeat']>time.time()-10)
