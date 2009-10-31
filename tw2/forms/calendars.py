"""
The MIT License

Copyright (c) 2007 MVP Sport Systems, LLC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

Portions of this document have been taken in part and modified from the original
tw.forms codebase written primarily by Alberto Valaverde

"""
import re
from datetime import datetime
import logging

import tw2.core as twc
from widgets import FormField

import formencode
from formencode.validators import *
from formencode.foreach import ForEach
from formencode.compound import *
from formencode.api import Invalid, NoDefault
from formencode.schema import Schema

__all__ = ["CalendarDatePicker", "CalendarDateTimePicker", "calendar_js", "calendar_setup"]

class DateTimeConverter(FancyValidator):

    """
    Converts Python date and datetime objects into string representation and back.
    """
    messages = {
        'badFormat': 'Invalid datetime format.',
        'empty': 'Please Enter a Date.',
    }
    if_missing = None
    def __init__(self, format = "%Y/%m/%d %H:%M", tzinfo=None, *args, **kwargs):
        super(FancyValidator, self).__init__(*args, **kwargs)
        self.format = format
        self.tzinfo = tzinfo
        
    def validate_python(self, value, state):
        return self.to_python(value, state)

    def _to_python(self, value, state):
        """ parse a string and return a datetime object. """
        if value and isinstance(value, (date, datetime)):
            return value
        else:
            try:
                tpl = time.strptime(value, self.format)
            except ValueError:
                raise Invalid(self.message('badFormat', state), value, state)
            # shoudn't use time.mktime() because it can give OverflowError,
            # depending on the date (e.g. pre 1970) and underlying C library
            return datetime(year=tpl.tm_year, month=tpl.tm_mon, day=tpl.tm_mday,
                            hour=tpl.tm_hour, minute=tpl.tm_min,
                            second=tpl.tm_sec, tzinfo=self.tzinfo)

    def _from_python(self, value, state):
        if not value:
            return None
        elif isinstance(value, datetime):
            # Python stdlib can only handle dates with year greater than 1900
            if value.year <= 1900:
                return strftime_before1900(value, self.format)
            else:
                return value.strftime(self.format)
        else:
            return value

_illegal_s = re.compile(r"((^|[^%])(%%)*%s)")

def _findall(text, substr):
    # Also finds overlaps
    sites = []
    i = 0
    while 1:
        j = text.find(substr, i)
        if j == -1:
            break
        sites.append(j)
        i = j+1
    return sites

def strftime_before1900(dt, fmt):
    """
    A strftime implementation that supports proleptic Gregorian dates before 1900.

    @see: http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/306860
    """
    import datetime
    if _illegal_s.search(fmt):
        raise TypeError("This strftime implementation does not handle %s")
    if dt.year > 1900:
        return dt.strftime(fmt)

    year = dt.year
    # For every non-leap year century, advance by
    # 6 years to get into the 28-year repeat cycle
    delta = 2000 - year
    off = 6*(delta // 100 + delta // 400)
    year = year + off

    # Move to around the year 2000
    year = year + ((2000 - year)//28)*28
    timetuple = dt.timetuple()
    s1 = time.strftime(fmt, (year,) + timetuple[1:])
    sites1 = _findall(s1, str(year))

    s2 = time.strftime(fmt, (year+28,) + timetuple[1:])
    sites2 = _findall(s2, str(year+28))

    sites = []
    for site in sites1:
        if site in sites2:
            sites.append(site)

    s = s1
    syear = "%4d" % (dt.year,)
    for site in sites:
        s = s[:site] + syear + s[site+4:]
    return s

setup_calendar = twc.JSFuncCall(function="Calendar.setup")

log = logging.getLogger(__name__)

calendar_css = twc.CSSLink(
    modname='tw2.forms', filename='static/calendar/calendar-system.css')
calendar_js = twc.JSLink(
    modname='tw2.forms', filename='static/calendar/calendar.js')
calendar_setup = twc.JSLink(
    resources=[calendar_js],
    modname='tw2.forms', filename='static/calendar/calendar-setup.js')

class CalendarDatePicker(FormField):
    """
    Uses a javascript calendar system to allow picking of calendar dates.
    The date_format is in mm/dd/yyyy unless otherwise specified
    """
    resources = [calendar_css, calendar_js, calendar_setup]
    template = "tw2.forms.templates.calendar"
    calendar_lang = twc.Param("Default Language to use in the Calendar", default='en')
    not_empty = twc.Param("Allow this field to be empty", default=True)
    button_text = twc.Param("Text to display on Button", default="Choose")
    date_format = twc.Param("Date Display Format", default="%m/%d/%Y")
    picker_shows_time = twc.Param('Picker Shows Time', default=False)
    tzinfo = twc.Param('Time Zone Information', default=None)
#    validator = None
    default = twc.Param('Default value for the widget', default=None)

    def get_calendar_lang_file_link(self, lang):
        """
        Returns a CalendarLangFileLink containing a list of name
        patterns to try in turn to find the correct calendar locale
        file to use.
        """
        fname = 'static/calendar/lang/calendar-%s.js' % lang.lower()
        return twc.JSLink(modname='tw2.forms',
                      filename=fname)

    @classmethod
    def post_define(cls):
        if cls.default is None and cls.not_empty:
            cls.default = lambda: datetime.now()
        cls.validator = cls.validator or DateTimeConverter(
            format=cls.date_format, not_empty=cls.not_empty,
            tzinfo=cls.tzinfo
            )

    def prepare(self):
#        if not self.value:
#            self.value = self.default()
        super(CalendarDatePicker, self).prepare()
        log.debug("Value received by Calendar: %r", self.value)
        
        try:
            self.strdate = self.value.strftime(self.date_format)
        except AttributeError:
            self.strdate = self.value
        options = dict(
            inputField = self.id,
            ifFormat = self.date_format,
            button = self.id + '_trigger',
            showsTime = self.picker_shows_time,
            )
        setup_calendar.args = options
        self.resources.append(setup_calendar)
        self.resources.append(self.get_calendar_lang_file_link(self.calendar_lang))


class CalendarDateTimePicker(CalendarDatePicker):
    """
    Use a javascript calendar system to allow picking of calendar dates and
    time.
    The date_format is in mm/dd/yyyy hh:mm unless otherwise specified
    """
    messages = {
        'badFormat': 'Invalid datetime format.',
        'empty': 'Please Enter a Date and Time.',
    }
    date_format = "%Y/%m/%d %H:%M"
    picker_shows_time = True