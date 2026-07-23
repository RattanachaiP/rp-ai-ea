from collections.abc import Mapping
from ._helpers import boolean, value
class SessionExtractor:
 def extract(self,evidence:Mapping[str,object])->dict[str,object]:
  session=str(value(evidence,"session","")).upper().replace(" ","_")
  return {"asia": boolean(value(evidence,"asia")) or session=="ASIA", "london": boolean(value(evidence,"london")) or session=="LONDON", "new_york": boolean(value(evidence,"new_york")) or session=="NEW_YORK", "overlap": boolean(value(evidence,"overlap")) or session=="OVERLAP", "pre_news":boolean(value(evidence,"pre_news")), "post_news":boolean(value(evidence,"post_news"))}
