from datetime import date, timedelta
from typing import List

def weekly_dates(start_date: date, weeks: int) -> List[date]:
    return [start_date + timedelta(days=i * 7) for i in range(weeks)]
