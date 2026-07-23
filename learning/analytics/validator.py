from .models import AnalyticsReport
def validate(report):
 if not isinstance(report,AnalyticsReport): raise TypeError("INVALID_ANALYTICS_REPORT")
 report.to_dict(); return report
