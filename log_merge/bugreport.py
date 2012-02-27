#!/usr/bin/python
#
#Usage:
# $./bugreport.py bugreport.txt [--tz=-6]> combined.txt
# The order of files doesn't affect the result.
# The script guesses the time zone from your computer's settings.
# Set timezone with --tz if the guess is wrong.
#
# Change Logs
#=================================================================
#Nov-16-2010    Peng Liu        Initial Version

import os, sys, re, time, linecache, copy
import datetime
from optparse import OptionParser
from datetime import timedelta

# Change this if the format of output can't pleasure you
line_format = "{tag}:{log_line}"

TIME_FORMAT = "%Y/%m/%d %H:%M:%S.%f"
TIME_PATTERN = re.compile('(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}):(\d+).(\d{6})')

# To change this means you've to change the way to guess time in main()
BUGREPORT_PATTERN =  "== dumpstate: (\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):\d{2}"
POSITION = 2
BUGREPORT_TIME = '{0}/01/01 00:00:00.000000'

#This is specific to bugreport.py.
#In fact, session's name isn't bound to starter or log type.  For
#example, when we are merging several files, the session name would be
#file name, and all the session types could all be the same, logcat.
session_defintions = [
    ["SYSTEM LOG", "^------ SYSTEM LOG",    "^------ ",  "LOGCAT LOG"],
    ["EVENT LOG",  "^------ EVENT LOG",     "^------ ",  "LOGCAT LOG"],
    ["RADIO LOG",  "^------ RADIO LOG",     "^------ ",  "LOGCAT LOG"],
    ["KERNEL LOG", "^------ KERNEL LOG",    "^------ ",  "KERNEL LOG"]
    ]

DEFAULT_BOOTTIME = "1970/01/01 00:00:00.000000"

LOGTYPE_DEFINITIONS = [
    ["LOGCAT LOG",      'datetime',     '{byear}/{0}/{1} {2}:{3}:{4}.{5}000',   '^(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3})',    None],
    ["KERNEL LOG",      'timedelta',    '0000/00/00 00:00:{0}.{1}',                   '^<\d>\[ *(\d+)\.(\d+)\]',                              [
            ['{0}/{1}/{2} {3}:{4}:{5}.000000', 'cpcap_rtc cpcap_rtc: setting system clock to (\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2}) UTC'],
            ['{0}/{1}/{2} {3}:{4}:{5}.{6}', '.*suspend: exit suspend, .* \((\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{6})\d{3} UTC\)']
            ]
     ]
    ]

DEBUG = 0
def dprint(f):
    if DEBUG == 1:
        sys.stderr.write("%s\n" % f)

def iprint(f):
    sys.stderr.write("%s\n" % f)

class UserExit(Exception):
    '''Raise this when the user wants to exit'''
    def __init__(self, reason):
        Exception.__init__(self)
        self.reason = reason

class BootTime:
    def __init__(self, tz):
        self.timezone = datetime.timedelta(days=0, hours=0, seconds=tz)

    def setboottime(self, bt):
        self.boottime = bt

    def getboottime(self):
        return self.boottime

class Session(object):
    def __init__(self, name, url, session_type, starter, finisher, boottime, start=-1):
        self.name = name
        self.url = url
        self.starter = re.compile(starter)
        self.finisher = re.compile(finisher)
        self.start = start
        self.current = start

        self.boottime = boottime
        self.session_type = session_type

    def set_start(self, n):
        '''To make it fast to merge bugreport,
        you need to search the start of the session,
        and set it with this function.'''
        self.start = n
        if self.current < n:
            self.current = n

    def __iter__(self):
        if self.start < 0:
            ln = 1
            while True:
                l = linecache.getline(self.url, ln)
                if len(l) == 0:
                    break;
                if self.starter.search(l):
                    break
                ln += 1
            self.start = ln

        self.current = self.start
        return self

    def next(self):
        '''Returns a tuple (time, line)'''
        ln = self.current

        l = linecache.getline(self.url, ln)
        if len(l) == 0:
            dprint("session %s: end of file" % self.name)
            raise StopIteration

        if self.finisher and self.finisher.search(l):
            dprint("session %s: find finisher at %d" % (self.name, ln))
            raise StopIteration

        t = self.session_type.parselog(l, self.boottime)
        ln += 1
        self.current = ln
        return (t, l[0:-1])

    def refresh(self):
        self.current = self.start

class SessionType:
    def __init__(self, l):
        self.type = l[0]
        self.timestamp_format = l[2]
        self.timestamp_pattern = re.compile(l[3])
        self.timestamp_type = l[1]
        self.timemodifier = list()
        if l[4]:
            for i in l[4]:
                self.timemodifier.append((i[0], re.compile(i[1])))

    def parselog(self, l, boottime):
        '''return a timestamp
        CAUTION: b(basetime) can be modified'''
        b = boottime.getboottime()
        tz = boottime.timezone
        # Parse the time stamp of this line.
        m = self.timestamp_pattern.search(l)
        if m is None:
            return copy.copy(boottime.getboottime())

        ts = self.timestamp_format.format(*(m.groups()), byear=b.year)
        t = None
        current_time = None

        if self.timestamp_type is 'timedelta':
            n = TIME_PATTERN.search(ts)
            assert(n)
            t = datetime.timedelta(days=int(n.groups()[2]),
                                   hours=int(n.groups()[3]),
                                   minutes=int(n.groups()[4]),
                                   seconds=int(n.groups()[5]),
                                   microseconds=int(n.groups()[6])
                                   )
            current_time = b + t
        else:
            current_time = datetime.datetime.strptime(ts, TIME_FORMAT)
            t = current_time - b

        # If the time is going to be changed in this line.
        for formatted,pattern  in self.timemodifier:
            n = pattern.search(l)
            if n is not None:
                current_time = datetime.datetime.strptime(formatted.format(*n.groups()), TIME_FORMAT)
                current_time = current_time - tz
                boottime.setboottime(current_time - t)
                break

        return current_time

def usage():
    sys.stderr.write("Usage: %s [--tz=<timezone in second or in hour>] bugreport.txt\n" % sys.argv[0])

def args_and_env():
    parser = OptionParser()
    parser.add_option("-t", "--tz", dest="tz", default="46800", help="")
    (options, args) = parser.parse_args(sys.argv)
    tz = float(options.tz)
    f = args[1]

    if tz < 30:
        tz = tz * 3600
    if tz == 46800:
        tz = time.altzone
        sys.stderr.write('You didn\'t specify a timezone for your logs. I guess it\'s %d hours late than UTC\n'%(tz/3600))
        sys.stderr.write('If it isn\'t the one you want to applied to the logs, enter n and restart the script with a timezone, like:\n')
        usage()
        while True:
            sys.stderr.write('Continue with timezone %d?[Y/n]\n'%(tz/3600))
            l = sys.stdin.readline()
            if len(l) == 1:
                break
            else:
                m = re.match('[Yy]', l)
                if m is not None:
                    break
                m = re.match('[Nn]', l)
                if m is not None:
                    raise UserExit("tz")

    return (tz, f)

def main():
    try:
        (time_zone, bugreport) = args_and_env()
        f = open(bugreport, "r")

    except:
        usage()
        return(1)

    # Guess the year.
    global_boottime = BootTime(time_zone)
    l = linecache.getline(bugreport, POSITION)
    if len(l) == 0:
        iprint("Can't find the header of a bugreport file! ")
        return(1)

    m = re.match(BUGREPORT_PATTERN, l)
    if m is not None:
        global_boottime.setboottime(datetime.datetime.strptime(BUGREPORT_TIME.format(*m.groups()), TIME_FORMAT))
    else:
        global_boottime.setboottime(datetime.datetime.strptime(BUGREPORT_TIME.format("1970"), TIME_FORMAT))

    # Construct sessions and session types.

    session_types = dict()
    for i in LOGTYPE_DEFINITIONS:
        session_types[i[0]] =SessionType(i)
    sessions = dict()
    for i in session_defintions:
        ss = Session(i[0], bugreport, session_types[i[3]], i[1], i[2], global_boottime)
        sessions[i[0]] = ss

    # To find each session's scope.
    # This would make the whole merging scan the file twice. But this
    # is not a issue - even if we make a single scan and then sort the
    # line numbers, to print out the result still needs another scan.
    current_session = None
    line_number = 1
    l = linecache.getline(bugreport, line_number)
    while len(l) != 0:
        if current_session:
            if current_session.finisher.search(l):
                dprint("session %s ends at %d" % (current_session.name, line_number))
                current_session = None
                continue

        for i in sessions.values():
            m = i.starter.search(l)
            if m is not None:
                current_session = i
                current_session.set_start(line_number+1)
                dprint("session %s starts at %d" % (current_session.name, line_number+1))
        line_number += 1
        l = linecache.getline(bugreport, line_number)

    # Print the oldest lines, and then read a new line from file
    time_lines = dict()
    times = list()
    sessions_to_be_read = sessions.keys()
    while len(sessions_to_be_read) != 0:

        for f in sessions_to_be_read:
            try:
                t,l = sessions[f].next()
            except StopIteration, e:
                dprint('Finished session %s: %s' % (f, e))
                del sessions[f]
                continue

            if t in time_lines.keys():
                time_lines[t].append((f, l))
            else:
                time_lines[t] = [(f, l)]
                for i in range(0,len(times)):
                    if t < times[i]:
                        times.insert(i, t)
                        break
                if t not in times:
                    times.append(t)

        sessions_to_be_read = list()

        if len(times) == 0:
            sys.stderr.write('All Set. Exiting...\n')
            return

        for f,l in time_lines[times[0]]:
            print('%s:%s' % (f, l))
            if f not in sessions_to_be_read:
                sessions_to_be_read.append(f)

        time_lines[times[0]] = None
        del time_lines[times[0]]
        del times[0]


if __name__ == '__main__':
    sys.exit(main())
