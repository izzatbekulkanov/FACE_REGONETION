from datetime import datetime
from django.utils.timezone import make_aware

def convert_timestamp_to_date(timestamp):
    """ ⏳ Timestamp'ni DateField formatiga o‘tkazish """
    return datetime.utcfromtimestamp(timestamp).date() if timestamp else None

def convert_timestamp_to_datetime(timestamp):
    """ ⏳ API timestamp ma'lumotini Django'ga mos formatga o‘tkazish """
    return make_aware(datetime.utcfromtimestamp(timestamp)) if timestamp else None
