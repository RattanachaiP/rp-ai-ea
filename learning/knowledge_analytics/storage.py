"""Append-only PR173 report storage under learning_data/knowledge_analytics."""
from __future__ import annotations
from pathlib import Path
import os, tempfile, json
from .models import KnowledgeAnalyticsReport

class KnowledgeAnalyticsRepository:
    def __init__(self, root='learning_data'):
        self.root=Path(root)/'knowledge_analytics'; self.root.mkdir(parents=True,exist_ok=True)
    def path_for(self, analytics_uuid): return self.root/f'report_{analytics_uuid}.json'
    def save(self, report: KnowledgeAnalyticsReport):
        path=self.path_for(report.analytics_uuid); data=json.dumps(report.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if path.exists():
            if path.read_bytes()==data: return path
            raise FileExistsError('APPEND_ONLY_REPORT_COLLISION')
        fd,tmp=tempfile.mkstemp(prefix='.report_',suffix='.tmp',dir=self.root)
        try:
            with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
            try: os.link(tmp,path)
            except FileExistsError:
                if path.read_bytes()!=data: raise FileExistsError('APPEND_ONLY_REPORT_COLLISION')
            finally: os.unlink(tmp)
        except BaseException:
            if os.path.exists(tmp): os.unlink(tmp)
            raise
        return path
    def load(self, analytics_uuid):
        return KnowledgeAnalyticsReport.from_dict(json.loads(self.path_for(analytics_uuid).read_text(encoding='utf-8')))
    def history(self):
        return tuple(self.load(p.stem.removeprefix('report_')) for p in sorted(self.root.glob('report_*.json')))
