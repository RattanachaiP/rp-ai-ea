"""Offline command entry point; no runtime, broker, or network dependency."""
from __future__ import annotations
import argparse, json
from learning.knowledge.reader import KnowledgeReader
from learning.knowledge.repository import KnowledgeRepository
from .engine import KnowledgeAnalyticsEngine
from .repository import AnalyticsRepository
def main():
 p=argparse.ArgumentParser(); p.add_argument('--knowledge-path',default='learning_data'); p.add_argument('--analytics-path',default='learning_data'); p.add_argument('--no-persist',action='store_true'); p.add_argument('--report-json'); args=p.parse_args()
 repo=None if args.no_persist else AnalyticsRepository(args.analytics_path)
 report=KnowledgeAnalyticsEngine(KnowledgeReader(KnowledgeRepository(args.knowledge_path)),repo).analyze()
 payload=json.dumps(report.to_dict(),sort_keys=True,indent=2)
 if args.report_json: open(args.report_json,'w',encoding='utf-8').write(payload+'\n')
 else: print(payload)
if __name__=='__main__': main()
