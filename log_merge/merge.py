#!/usr/bin/python
#Usage: 
# $./merge.py log.kernel.txt log.main.txt log.radio.txt [--tz=21600]> combined.txt
# The order of files doesn't affect the result.
# Kenrel messages can be automatically detected. 
# Set timezone with --tz if the timezone guess is wrong.

# 
# ChangeLogs
#=======================================================================
#Oct-14-2010    Peng Liu        Initial Version
#Oct-15-2010    Peng Liu        Bug fix: UTC - tz is the localtime.
#Oct-21-2010    Peng Liu        Handle time stamp wrapping-around.
#Nov-15-2010    Peng Liu        Fix the comments about timezone,
#                               and accept value in hour as tz value.
#Jun-23-2011    Thomas Buhot    Bug fix: less restrictive regex to find kernel resume time
#                               Bug fix: kernel microsonds read on 6 digits
#                               Kernel time format identical with logcat time format
#Jun-28-2011    Thomas Buhot    Bug fix: change RTC regex pattern
#                               Bug fix: change suspend / resume pattern
#Nov-30-2011    Peng Liu        Improvement: 
import os, sys, re, datetime, time
from optparse import OptionParser

SOFTWARE_NAME = 'merge'
AUTHOR = 'Peng Liu-a22543@motorola.com'
LAST_UPDATE = 'Nov 30, 2011'
IMPOSSIBLE_TIMEZONE = "54000"

KERNEL_TIME_STAMP = '^<\d>\[ *(\d+)\.(\d+)\] (.*)'
LOGCAT_TIME_STAMP = '^(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3}) (.*)'
RTC_TIME_STAMP = \
    ' \(*(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})(\.\d{9})* UTC'

FILE_TYPES = dict(
    LOGCAT_LOG = 0,
    KERNEL_LOG = 1
    )

class Logfile:

    class NotGoodLogException(Exception):
        pass

    kernelbasetime = datetime.datetime(datetime.MAXYEAR, 1, 1)

    def __try_reset_kernelbasetime__(self, l):
        """
        Tries to find the RTC time from the line, so that the kernel base(boot)
        time is therefore updated.
        Returns tulip (new_kernelbasetime, kernel_time, msg_body)
        """
        b = None
        m = self.rtc_time_stamp.search(l)
        if m is None:
            return None
        if m.group(7) is not None:
            microsecond = m.group(7)[1:7]
        else:
            microsecond = '0'
        b = datetime.datetime(year=int(m.group(1)),
                              month=int(m.group(2)),
                              day=int(m.group(3)),
                              hour=int(m.group(4)),
                              minute=int(m.group(5)),
                              second=int(m.group(6)),
                              microsecond=int(microsecond)
                              )
        debug_print('Got the RTC setting %s in %s'%(b,self.filename))
        n = self.timestamp_pattern.match(l)
        t = datetime.timedelta(days=0,
                               hours=0,
                               seconds=int(n.group(1)),
                               microseconds=int(n.group(2)))
        b = b - t - datetime.timedelta(days=0, hours=0, seconds=self.tz)
        return b

    def __init__(self, filename, tz=time.altzone, conv=False):
        self.tz = tz
        self.filename = filename
        self.file = open(filename, 'r')
        self.conv = conv

        # Determine if self.file is a kernel log or logcat log
        n = None
        m = None
        while (n is None) and (m is None):
            l = self.file.readline()
            if len(l) == 0:
                self.file.close()
                self.file = None
                raise Logfile.NotGoodLogException
            n = re.match(KERNEL_TIME_STAMP, l)
            m = re.match(LOGCAT_TIME_STAMP, l)

        if n is None:
            # this is a logcat file. timezone is useless
            self.tz = 0
            self.type = FILE_TYPES['LOGCAT_LOG']
            self.timestamp_pattern =\
                re.compile('^(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3})')
            self.file.seek(0)
            return

        # this is a kernel log
        self.type = FILE_TYPES['KERNEL_LOG']
        self.timestamp_pattern = re.compile(KERNEL_TIME_STAMP)
        self.rtc_time_stamp = re.compile(RTC_TIME_STAMP)
#        self.boot_time_pattern =\
#            re.compile('.* (\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2}) UTC')
#        self.resume_time_pattern =\
#            re.compile('.* \((\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d+) UTC\)')
        self.dmesg_body = re.compile('\] .*')

        # try find the kernelbasetime
        while len(l) != 0:
            b = self.__try_reset_kernelbasetime__(l)
            if b is None:
                l = self.file.readline()
                continue
            if (abs(b - Logfile.kernelbasetime) > \
                    datetime.timedelta(days=0,seconds=1)):
                Logfile.kernelbasetime = b
            break

        if len(l) == 0:
            debug_print('Can\'t find a valid kernelbasetime in %s\n'%self.filename);
        else:
            debug_print('boot time is %s'%Logfile.kernelbasetime)
        # finish finding the kernelbasetime
        self.file.seek(0)
        return

    def __del__(self):
        if self.file:
            self.file.close()

    def get_datetime(self):
        l = self.file.readline()
        if len(l) == 0:
            t = datetime.datetime(datetime.MAXYEAR, 1, 1)
            return t,l

        n = self.timestamp_pattern.match(l)
        if n is None:
            t = datetime.datetime(datetime.MINYEAR, 1, 1)
            return t,l

        if self.type == FILE_TYPES['KERNEL_LOG']:
            #this is a kernel log
            b = self.__try_reset_kernelbasetime__(l)
            if b:
                Logfile.kernelbasetime = b
            t = Logfile.kernelbasetime + datetime.timedelta(seconds=int(n.group(1)), microseconds=int(n.group(2)))
            if (self.conv):
                body = n.group(3)
                l = '%02d-%02d %02d:%02d:%02d.%03d %s\n' %(t.month,t.day,t.hour,t.minute,t.second,t.microsecond/1000,body[0:])
            debug_print("kernel log time stampe is %s"%t)
        else:
            t = datetime.datetime(int(Logfile.kernelbasetime.year), int(n.group(1)), int(n.group(2)), int(n.group(3)), int(n.group(4)), int(n.group(5)), int(n.group(6))*1000)
        return t,l

debug = False
def debug_print(msg):
    if debug is True:
        sys.stderr.write(msg+os.linesep)
quiet = False
def error_print(msg):
    if quiet is False:
        sys.stderr.write(msg+os.linesep)

# version info.
error_print(SOFTWARE_NAME+' '+LAST_UPDATE+os.linesep)
error_print(AUTHOR+os.linesep)

if __name__ == '__main__':
    #parsing options
    if len(sys.argv) < 3:
        error_print('Too few argument. Exiting...')
        sys.exit(1)

    parser = OptionParser()
    parser.add_option("-t", "--tz", dest="tz", default=IMPOSSIBLE_TIMEZONE,
                      help="")
    parser.add_option("-v", "--verb", dest="verb", default="0", help="")
    parser.add_option("-q", "--quiet", action="store_true", dest="quiet",
                      default=False, help="")
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                      default=False, help="")
    parser.add_option("-c", "--convert", action="store_true", dest="conv",
                      default=False, help="")
    parser.add_option("-f", "--filename", action="store_true", dest="filename",
                      default=False, help="")
    (options, args) = parser.parse_args(sys.argv)
    tz = float(options.tz)
    verb = int(options.verb)
    quiet = options.quiet
    conv = options.conv
    debug = options.debug

    if tz < 30:
        tz = tz * 3600
    if tz == float(IMPOSSIBLE_TIMEZONE):
        tz = time.altzone
        if not quiet:
            error_print('You didn\'t specify a timezone for your logs. I guess it\'s %d hours late than UTC'%(tz/3600))
            error_print('If it isn\'t the one you want to applied to the logs, enter n and restart the script with a timezone, like:')
            error_print('\tmerge.py <file1> <file2> [file3 [...]] --tz <timezone in second or in hour>')
            while True:
                error_print('Continue with timezone %d?[Y/n]'%(tz/3600))
                l = sys.stdin.readline()
                if len(l) == 1:
                    break
                else:
                    m = re.match('[Yy]', l)
                    if m is not None:
                        break
                    m = re.match('[Nn]', l)
                    if m is not None:
                        sys.exit(0)

    # start merging: preprocessing files
    error_print('Merging starts...')
    files = dict()
    for i in args[1:]:
        if os.access(i, os.R_OK):
            try:
                f = Logfile(i, tz, conv)
            except Logfile.NotGoodLogException:
                error_print('%s is not a good logfile' % i)
                continue            
            files[i] = f
        else:
            error_print('%s can\'t be read' % i)

    #print the oldest lines, and then read a new line from file
    file_line = dict()
    time_file = dict()
    times = list()
    tmp_list = files.values()

    while len(tmp_list) != 0:

        for f in tmp_list:

            t,l = f.get_datetime()
            if len(l) == 0:
                del file_line[f.filename]
                del files[f.filename]
                continue

            if t in time_file.keys():
                time_file[t].append(f)
            else:
                time_file[t] = [f]
                for i in range(0,len(times)):
                    if t <= times[i]:
                        times.insert(i, t)
                        break
                if t not in times:
                    times.append(t)

            file_line[f.filename] = l

        if len(times) == 0:
            error_print('All Set. Exiting...')
            sys.exit(0)

        tmp_list = time_file[times[0]]

        for f in time_file[times[0]]:
            if not quiet:
                print('%s:\t%s' % (f.filename, file_line[f.filename])),
            else:
                print(file_line[f.filename]),

        time_file[times[0]] = None
        del time_file[times[0]]
        del times[0]

