import string,os,re,sys
from optparse import OptionParser
from xml.dom import minidom,Node

SOFTWARE_NAME = 'log parser'
AUTHOR = 'Peng Liu - <a22543@motorola.com>'
LAST_UPDATE = 'SEP 12, 2012'

################################################################################
# Global definitions
TOP = 5
UNKNOWN = 'UNKNOWN'
TIME_UNIT = 1000000000
VERBOSE = False
DEBUG = False
LAST = False
CSV = True
KERNEL_TIME_LIMIT = 131072.0
KERNEL_TIME_STAMP =\
    re.compile('^<\d>\[ *(\d+)\.(\d{6})[^\]]*\] (.*)')
LOGCAT_TIME_STAMP =\
    re.compile('^(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3}) (.*)')
MIN_INT = -sys.maxint - 1
################################################################################
# Debug functions
def __debug_print(msg):
    if DEBUG is True:
        sys.stderr.write('DEBUG: %s%s'%(msg,os.linesep))

quiet = False
def __warning_print(msg):
    if VERBOSE or DEBUG:
        sys.stderr.write('WARNING: %s%s'%(msg,os.linesep))

def __error_print(msg):
    if quiet is False:
        sys.stderr.write('ERROR: %s%s'%(msg,os.linesep))

def __usage():
    sys.stderr.write(
        '%sUSAGE: python -u pm_log_parser.py -p <platform> <dmesg.txt>%s'%
        (os.linesep,
         os.linesep
         ))
    sys.stderr.write('\t\tSummary statistics will be printed to stdout '+
                     'and <dmesg.txt>.csv has details.%s'%os.linesep)

################################################################################
# Facilities
def __current_time(c):
    return float(c['kernel_time_stamp']) + KERNEL_TIME_LIMIT *\
        c['kernel_time_wrapup_counter']

def __duration(s):
    return s.end_time - s.start_time + s.rtc_only

def __cost_capacity(s):
    if s.start_cc == MIN_INT or s.end_cc == MIN_INT:
        __warning_print('end capbility is not valid')
        return 0.0
    c = s.start_cc - s.end_cc
    if c < 0:
        __warning_print('cost < 0 when (%f - %f) for %s,%s from %s to %s'%(
                s.start_cc,
                s.end_cc,
                s.type,
                s.reason,
                s.start,
                s.end
                )
                        )
        c = 0.0
    return c

def __cost_CC(s):
    if s.start_cc == MIN_INT or s.end_cc == MIN_INT:
        __warning_print('cc is not valid')
        return 0.0
    c = s.end_cc - s.start_cc
    if c < 0:
        __warning_print('cost < 0 when (%f - %f) for %s,%s from %s to %s'%(
                s.start_cc,
                s.end_cc,
                s.type,
                s.reason,
                s.start,
                s.end
                )
                      )
        c = 0.0
    return c

def __cost_mA(s):
    if s.end_cc <= 0:
        __warning_print('cost < 0 when (%f - %f) for %s,%s from %s to %s'%(
                s.start_cc,
                s.end_cc,
                s.type,
                s.reason,
                s.start,
                s.end
                )
                      )
        c = 0.0
    else:
        c = __duration(s) * s.end_cc
    return c

__cost_func_name = None
def __cost(s, style = 'CC'):
    global __cost_func_name
    ret = 0
    if __cost_func_name == None:
        n = '__cost_%s'%style
        if n in globals().keys():
            __cost_func_name = globals()[n]
            ret = __cost_func_name(s)
    else:
        ret = __cost_func_name(s)
    return ret

def __cc_uah(string):
    return float(string)/1000

__cc_func_name = None
def __cc(string, style = 'uah'):
    global __cc_func_name
    ret = 0
    if __cc_func_name == None:
        n = '__cc_%s'%style
        if n in globals().keys():
            __cc_func_name = globals()[n]
            ret = __cc_func_name(string)
    else:
        ret = __cc_func_name(string)
    return ret

def add_onto_elem_in_dict(d, k, number=0, duration=0, cost=0, cost_duration=0):
    if k not in d.keys():
        d[k] = Sum(k)
    d[k].update(number, duration, cost, cost_duration)

def __init_cur(fobj_out):
    cur_state = dict()
    cur_state['state'] = UNKNOWN
    # This is for the last resume from successful suspend
    cur_state['resume_time'] = -1.0
    cur_state['resume_ts'] = UNKNOWN
    cur_state['resume_coulomb'] = MIN_INT
    # This is for the last suspend attempt, no matter if successful or not
    cur_state['susp_kicked_time'] = -1.0
    cur_state['susp_kicked_ts'] = 'UNKNOWN'
    # This is for the nearest suspend attempt
    cur_state['susp_kicked_coulomb'] = MIN_INT
    # This is for the nearest activating
    cur_state['activated_coulomb'] = MIN_INT
    cur_state['activated_time'] = -1.0
    cur_state['activated_ts'] = UNKNOWN
    # This is for tne nearest resume
    cur_state['active_wakelock'] = UNKNOWN
    cur_state['failed_device'] = UNKNOWN
    cur_state['wakeup_source'] = UNKNOWN
    cur_state['active_type'] = 'UNKNOWN'
    cur_state['active_reason'] = UNKNOWN
    # Kernel stamp and potential wrapping-up count
    cur_state['kernel_time_stamp'] = ''
    cur_state['kernel_time_wrapup_counter'] = 0
    cur_state['longest_wakelock_name'] = None
    cur_state['longest_wakelock_len'] = 0
    # Display state
    cur_state['display'] = UNKNOWN
    cur_state['wakeup_time'] = 0.0
    cur_state['sleep_time'] = 0.0
    cur_state['wakeup_ts'] = UNKNOWN
    cur_state['sleep_ts'] = UNKNOWN
    cur_state['sleep_coulomb'] = MIN_INT
    cur_state['wakeup_coulomb'] = MIN_INT
    cur_state['gptimer_stop_time'] = 0.0
    # CSV file and states
    cur_state['fobj_out'] = fobj_out
    cur_state['charging_start'] = -2.0
    cur_state['last_resume_time'] = -2.0
    # CPU1
    cur_state['cpu1_on'] = -2.0
    return cur_state

def time_and_body(line):
    n = KERNEL_TIME_STAMP.match(line)
    if n is None:
        return (None,None)
    return (n.groups()[0]+'.'+n.groups()[1],n.groups()[2])

################################################################################
# Global classes
class Sum(object):
    def __init__(self, name='', duration=0.0, cost=0.0, count=0):
        self.count = count
        self.duration = duration
        self.cost_duration = 0.0
        self.cost = cost
        self.name = name
    def count_inc(self):
        self.count += 1
    def duration_add(self, d):
        self.duration += d
    def cost_add(self, c):
        self.cost += c
    def update(self, count, duration, cost, cost_duration):
        self.count += count
        self.duration += duration
        self.cost += cost
        self.cost_duration += cost_duration
    def add(self, duration, cost, cost_duration):
        self.count += 1
        self.duration += duration
        self.cost += cost
        self.cost_duration += cost_duration

class Top(object):
    class Empty:
        pass
    def __init__(self, field, count = TOP):
        self.list = list()
        self.count = count
        self.field = field
        return
    def insert(self, obj):
        i = 0
        value = getattr(obj, self.field)
        count = min(self.count, len(self.list))
        while (i < count):
            v = float(getattr(self.list[i], self.field))
            if value > v:
                break
            i += 1
        if i < self.count:
            self.list.insert(i,obj)
            count = min(self.count, len(self.list))
            self.list = self.list[0:count]
        return
    def select(self, obj_list):
        for i in obj_list:
            self.insert(i)

class Session(object):
    def __init__(self,
                 start=UNKNOWN,
                 start_time=0,
                 end=UNKNOWN,
                 duration=0.0,
                 cost=0.0,
                 typ='UNKNOWN',
                 reason='UNKNOWN',
                 start_cc = MIN_INT
                 ):
        self.start = start
        self.end = end
        self.start_cc = start_cc
        self.end_cc = MIN_INT
        self.cost = cost
        self.duration = duration
        self.cost_duration = 0.0
        self.type = typ
        self.reason = reason
        self.start_time = start_time
        self.end_time = -1.0
        self.rtc_only = 0.0
        self.usb_time = 0
        self.cpu1_time = 0
    def debug_print(self):
        sys.stderr.write("start = %s%s"%(self.start, os.linesep))
        sys.stderr.write("end = %s%s"%(self.end, os.linesep))
        sys.stderr.write("type = %s%s"%(self.type, os.linesep))
        sys.stderr.write("reason = %s%s"%(self.reason, os.linesep))
        sys.stderr.write("start_cc = %.03f%s"%(self.start_cc, os.linesep))
        sys.stderr.write("end_cc = %.03f%s"%(self.end_cc, os.linesep))
        sys.stderr.write("cost = %.03f%s"%(self.cost, os.linesep))

class FullLogSession(Session):
    def __init__(self,
                 start=UNKNOWN,
                 start_time=0,
                 end=UNKNOWN,
                 duration=0.0,
                 cost=0.0,
                 typ=UNKNOWN,
                 reason = UNKNOWN):
        super(FullLogSession, self).__init__(
            start, start_time, end, duration, cost, typ, reason)
        self.discharge_sessions = list()
        self.display_sum = Sum()
        self.active_sum = Sum()
        self.suspend_sum = Sum()
        self.active_stats = dict()
        self.active_stats['BACKGROUND'] = dict()
        self.active_stats['ABORT'] = dict()
        self.active_stats['DEVICE'] = dict()
        self.active_stats['DISPLAYOFF'] = dict()
        self.blocker_stats = dict()
    def new_session(self, s):
        if s.type == 'DISPLAY':
            self.display_sum.add(s.duration, s.cost, s.cost_duration)
        else:
            add_onto_elem_in_dict(
                self.active_stats[s.type],
                s.reason,
                1,
                s.duration,
                s.cost,
                s.cost_duration
                )
            self.active_sum.add(s.duration, s.cost, s.cost_duration)
        self.cost_duration += s.cost_duration
        return
    def new_suspend_session(self, s):
        self.suspend_sum.add(s.duration, s.cost, s.duration)
        self.cost_duration += s.cost_duration
        self.rtc_only += s.rtc_only
        return

class DischargeSession(Session):
    def __init__(self,
                 start=UNKNOWN,
                 start_time=0,
                 end=UNKNOWN,
                 duration=0.0,
                 cost=0.0,
                 typ=UNKNOWN,
                 reason = UNKNOWN,
                 start_cc = MIN_INT
                 ):
        super(DischargeSession, self).__init__(
            start,
            start_time,
            end,
            duration,
            cost,
            typ,
            reason,
            start_cc
            )
        self.display_sum = Sum()
        self.active_sum = Sum()
        self.suspend_sum = Sum()
        self.active_stats = dict()
        self.active_stats['BACKGROUND'] = dict()
        self.active_stats['ABORT'] = dict()
        self.active_stats['DEVICE'] = dict()
        self.active_stats['DISPLAYOFF'] = dict()
        self.blocker_stats = dict()
        self.tops = dict()
        self.tops['cost_displayon'] = Top('cost')
        self.tops['duration_displayon'] = Top('duration')
        self.tops['cost_active'] = Top('cost')
        self.tops['duration_active'] = Top('duration')
        self.tops['cost_awoken'] = Top('cost')
        self.tops['duration_awoken'] = Top('duration')
        self.tops['cost_suspend'] = Top('cost')
        self.tops['duration_suspend'] = Top('duration')
    def new_session(self, s):
        if s.reason == 'displayon':
            self.display_sum.add(s.duration, s.cost, s.cost_duration)
            self.tops['cost_displayon'].insert(s)
            self.tops['duration_displayon'].insert(s)
        else:
            add_onto_elem_in_dict(
                self.active_stats[s.type],
                s.reason,
                1,
                s.duration,
                s.cost,
                s.cost_duration
                )
            self.active_sum.add(s.duration, s.cost, s.cost_duration)
            self.tops['cost_active'].insert(s)
            self.tops['duration_active'].insert(s)
        self.cost_duration += s.cost_duration
        return
    def new_suspend_session(self, s):
        self.suspend_sum.add(s.duration, s.cost, s.cost_duration)
        self.cost_duration += s.cost_duration
        self.rtc_only += s.rtc_only
        self.tops['cost_suspend'].insert(s)
        self.tops['duration_suspend'].insert(s)
        return

################################################################################
# Main Section Starts
REGEX = {
    # Linux standard info
    'freezing': # This might be the first indicator for suspend kicking off if suspend_coulomb is not present
        (re.compile('Freezing user space processes ...'),
         'freezing_regex_hook'),
    'aborted1':
        (re.compile('Freezing of tasks  aborted'),
         'aborted_regex_hook'),
    'aborted2':
        (re.compile('Freezing of user space  aborted'),
         'aborted_regex_hook'),
    'aborted3':
        (re.compile('suspend aborted....'),
         'aborted_regex_hook'),
    'failed_device':
        (re.compile('PM: Device ([^ ]+) failed to suspend'),
         'failed_device_regex_hook'),
    'resumed': # This is the indicator for last suspend session closing and the wakeup session can be opened
        (re.compile('suspend: exit suspend, ret = (-{0,1}\d+) \((\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{9}) UTC\)'),
         'resumed_regex_hook'),
    # Android
    'active_wakelock':
        (re.compile('active wake lock ([^, ]+),*'),
         'active_wakelock_regex_hook'),
    'display_sleep':
        # New display-off session can be started, but last display-on session not closed yet because we don't know cost
        (re.compile('request_suspend_state: sleep \(0->3\)'),
         'display_sleep_regex_hook'),
    'display_wakeup':
        # Display-on active session can be started, but last active session not finished yet because we don't know the cost
        (re.compile('request_suspend_state: wakeup \(3->0\)'),
         'display_wakeup_regex_hook'),
    'wakeup_wakelock':
        # When wakeup_source is not available, this is the wakeup_source
    (re.compile('wakeup wake lock: ([\w-]+)'),
     'wakeup_wakelock_regex_hook'),
    'suspend_duration':
        (re.compile('Suspended for (\d+)\.(\d+) seconds'),
         'suspend_duration_regex_hook'),
    # Motorola debug info
    'suspend_coulomb': # This is the first possible indicator for suspend, but not in user build. Last active session can be closed.
        (re.compile('pm_debug: suspend uah=(-{0,1}\d+)'),
         'suspend_coulomb_regex_hook'),
    'resume_coulomb': # This might not in user build
        (re.compile('pm_debug: resume uah=(-{0,1}\d+)'),
         'resume_coulomb_regex_hook'),
    'longest_wakelock': # Not in user build
        (re.compile('longest wake lock: \[([^\]]+)\]\[(\d+)\]'),
         'longest_wakelock_regex_hook'),
    'suspend_duration1':
        (re.compile('suspend: e_uah=-{0,1}\d+ time=(\d+)'),
         'suspend_duration_regex_hook'),
    'suspend_duration2':
        (re.compile('suspend: time=(\d+)'),
         'suspend_duration_regex_hook'),
    'display_sleep_coulomb': # Not in user build
        (re.compile('pm_debug: sleep uah=(-{0,1}\d+)'),
         'display_sleep_coulomb_regex_hook'),
    'display_wakeup_coulomb': # Not in user build
        (re.compile('pm_debug: wakeup uah=(-{0,1}\d+)'),
         'display_wakeup_coulomb_regex_hook'),
    }

BSP_REGEX = {
    # BSP
    'boot_start': 'booting_regex_hook',
    'wakeup_source_after_wakeuplock': 'wakeup_source_after_wakeuplock_regex_hook', # This is the first possible indicator for resume from successful suspend. Here wakeup session must be opened, but suspend not closed yet
    'wakeup_source_before_wakeuplock': 'wakeup_source_before_wakeuplock_regex_hook',
    'start_charging': 'charging_regex_hook',
    'stop_charging': 'discharging_regex_hook', # Last charge session can be close
    'deep_sleep': 'deep_sleep_regex_hook',
    'cpu1_off': 'cpu1_off_regex_hook',
    'cpu1_on': 'cpu1_on_regex_hook',
    }

def __missing_log_warning(s,c,e):
    __warning_print('%s session state is abnormal'%e)
    __warning_print('There might be log missing before %s'%c['kernel_time_stamp'])
    if DEBUG:
        __debug_print_all(s,c)
    return

def __missing_discharge(sessions, state):
    # It's a real one if charge is available
    if sessions['charge'] is not None:
        __error_missing_log(sessions, state, 'un charge')
        return # Never reach here
    __missing_log_warning(sessions, state, 'discharge')
    sessions['discharge'] = DischargeSession(
        start = sessions['full'].start,
        start_time = sessions['full'].start_time
        )
    state['charging_start'] = -1.0
    state['last_resume_time'] = sessions['full'].start_time
    return

def __missing_wakeup(sessions, state):
    __missing_log_warning(sessions, state, 'wakeup')
    if sessions['discharge'] is not None:
        sessions['wakeup'] = Session(
            start = sessions['full'].start,
            start_time = sessions['full'].start_time
        )
    else:
        sessions['wakeup'] = Sessions(
            start = state['kernel_time_stamp'],
            start_time = __current_time(state)
            )
    return

def __missing_suspend(sessions, state, matches = None):
    # It's a real one if charge is available
    if sessions['wakeup']:
        __error_missing_log(sessions, state, 'suspend')
        return # Never reach here
    __missing_log_warning(sessions, state,'suspend')
    sessions['suspend'] = Session(
        start = sessions['full'].start,
        start_time = sessions['full'].start_time
        )
    return

def __error_missing_log(sessions, state, string):
    __missing_log_warning(sessions, state, string)
    raise Exception("Missing Log!")

def __start_suspend(sessions, state, start_cc = MIN_INT):
    sessions['suspend'] = Session(
        start=state['kernel_time_stamp'],
        start_time=__current_time(state)
        )
    if start_cc:
        sessions['suspend'].start_cc = start_cc
    return

def __close_suspend(sessions, state):
    s = sessions['suspend']
    s.end = state['kernel_time_stamp']
    s.end_time = __current_time(state)
    s.duration = __duration(s)
    s.cost = __cost(s)
    if s.cost != 0:
        s.cost_duration = s.duration
    sessions['full'].new_suspend_session(s)
    if sessions['discharge']:
        sessions['discharge'].new_suspend_session(s)
    sessions['suspend'] = None
    return

def __start_active(sessions, state, typ = UNKNOWN, reason = UNKNOWN, cc = MIN_INT):
    sessions['active'] = Session(
        start=state['kernel_time_stamp'],
        start_time=__current_time(state),
        typ=typ,
        reason=reason
        )
    sessions['active'].start_cc = cc
    sessions['active'].end_cc = MIN_INT
    return

def __cancel_suspend(sessions, state):
    sessions['suspend'] = None
    return

def __close_active(sessions, state):
    s = sessions['active']
    s.end = state['kernel_time_stamp']
    s.end_time = __current_time(state)
    s.duration = __duration(s)
    s.cost = __cost(s)
    if s.cost != 0:
        s.cost_duration = s.duration
    sessions['full'].new_session(s)
    if sessions['discharge']:
        sessions['discharge'].new_session(s)
    if sessions['wakeup']:
        sessions['wakeup'].cost += s.cost
        sessions['wakeup'].cost_duration += s.cost_duration
    sessions['active'] = None
    return

def __start_charge(sessions, state):
    if sessions['charge'] is None:
        sessions['charge'] = Session(
            start = state['kernel_time_stamp'],
            start_time = __current_time(state)
            )
    return

def __close_charge(sessions, state):
    sessions['charge'] = None
    return

def __start_discharge(sessions, state):
    sessions['discharge'] = DischargeSession(
        start = state['kernel_time_stamp'],
        start_time = __current_time(state)
        )
    state['charging_start'] = -1.0
    state['last_resume_time'] = __current_time(state)
    return

def __close_discharge(sessions, state):
    if sessions['discharge'] is not None:
        s = sessions['discharge']
        s.end = state['kernel_time_stamp']
        s.end_time = __current_time(state)
        s.duration = __duration(s)
        sessions['full'].discharge_sessions.append(s)
        sessions['discharge'] = None
    return

def __start_wakeup(sessions, state, reason = None):
    sessions['wakeup'] = Session(
        start = state['kernel_time_stamp'],
        start_time = __current_time(state)
        )
    if reason:
        sessions['wakeup'].reason = reason
    return

def __close_wakeup(sessions, state):
    s = sessions['wakeup']
    if s.end_time < 0:
        s.end = state['kernel_time_stamp']
        s.end_time = __current_time(state)
        s.duration = __duration(s)
    if sessions['discharge']:
        sessions['discharge'].tops['cost_awoken'].insert(s)
        sessions['discharge'].tops['duration_awoken'].insert(s)
    sessions['wakeup'] = None
    return

def __start_displayon(sessions, state):
    sessions['active'] = Session(
        start = state['kernel_time_stamp'],
        start_time = __current_time(state),
        typ = 'DISPLAY',
        reason = 'displayon'
        )
    return

def __close_last_active(sessions, state, cc = MIN_INT):
    s = sessions['last_active']
    if cc:
        s.end_cc = cc
    s.cost = __cost(s)
    s.duration = __duration(s)
    if s.cost > 0:
        s.cost_duration = s.duration
    sessions['full'].new_session(s)
    if sessions['discharge']:
        sessions['discharge'].new_session(s)
    if sessions['wakeup']:
        sessions['wakeup'].cost += s.cost
        sessions['wakeup'].cost_duration += s.cost_duration
    sessions['last_active'] = None
    return

def __start_displayoff(sessions, state):
    sessions['active'] = Session(
        start = state['kernel_time_stamp'],
        start_time = __current_time(state),
        typ = 'DISPLAYOFF',
        reason = 'displayoff'
        )
    return

def __csv_active(sessions, state):
    duration = 0.0
    cost = 0.0
    avg = 0.0
    l = 0.0
    if state['last_resume_time'] >= 0:
        l = __current_time(state) - state['last_resume_time']
        state['last_resume_time'] = -1.0
        if sessions['active']:
            cost = __cost(sessions['active'])
            duration = __current_time(state) - sessions['active'].start_time
            if duration != 0:
                avg = cost * 3600 / duration
    elif state['last_resume_time'] == -2.0:
        state['last_resume_time'] = -1.0
    elif state['last_resume_time'] == -1.0:
        __missing_log_warning(sessions, state, 'resume')
    if state['fobj_out']:
        state['fobj_out'].write("%f,%.02f,"%(l, avg))
    return

def __csv_suspend(sessions, state, status_str = None):
    duration = 0
    wakeup_source = 'UNKNOWN'
    cost = 0
    avg = 0
    start = sessions['full'].start
    status = 'pass'
    if status_str is None:
        if sessions['suspend']:
            duration = __current_time(state) -\
                sessions['suspend'].start_time + sessions['suspend'].rtc_only
            if sessions['wakeup']:
                wakeup_source = sessions['wakeup'].reason
            cost = sessions['suspend'].cost
            start = sessions['suspend'].start
            if duration != 0:
                avg = cost * 3600 / duration
    else:
        wakeup_source = ''
        status = status_str
        if sessions['suspend']:
            duration = __current_time(state) - sessions['suspend'].start_time
            start = sessions['suspend'].start
        elif sessions['charge']:
            duration = __current_time(state) - sessions['charge'].start_time
            start = sessions['charge'].start
    state['last_resume_time'] = __current_time(state)
    if state['fobj_out']:
        state['fobj_out'].write("%s,%f,%s,%s,%.02f,%s\n"%
                                (start,
                                 duration,
                                 state['kernel_time_stamp'],
                                 status,
                                 avg,
                                 wakeup_source,
                                 )
                                )
    return


def booting_regex_hook(sessions, state, matches):
    __start_discharge(sessions, state)
    __start_wakeup(sessions, state)
    __start_active(sessions, state, 'BACKGROUND', 'bootup')
    state['last_resume_time'] = __current_time(state)
    return

def freezing_regex_hook(sessions, state, matches):
    # To compensate log if not started from boot-up
    if sessions['discharge'] is None:
        __missing_discharge(sessions, state)
    if sessions['wakeup'] is None:
        __missing_wakeup(sessions, state)
        if CSV:
            __csv_active(sessions, state)
    # If last active session hasn't been closed, close it here
    if sessions['last_active']:
        __close_last_active(sessions, state)
    if sessions['active']:
        if CSV:
            __csv_active(sessions, state)
        # if active is still here, we might not have coulomb logging
        __close_active(sessions, state)
    if sessions['suspend'] is None:
        __start_suspend(sessions, state)
    return

def aborted_regex_hook(sessions, state, matches):
    # Don't have to check other sessions because this line has been processed by freezing_regex_hook
    # Starts next active
    if CSV:
        __csv_suspend(sessions, state, 'freeze_abort')
    if sessions['discharge'] is None:
        __missing_discharge(sessions, state)
    if sessions['suspend'] is None:
        __missing_suspend(sessions, state, matches)
    __start_active(sessions,
                   state,
                   'ABORT',
                   state['active_wakelock'],
                   sessions['suspend'].start_cc)
    sessions['active'].start = sessions['suspend'].start
    sessions['active'].start_time = sessions['suspend'].start_time
    __cancel_suspend(sessions, state)
    return

def failed_device_regex_hook(sessions, state, matches):
    # Starts next active
    if CSV:
        __csv_suspend(sessions, state, 'device_failure')
    if sessions['discharge'] is None:
        __missing_discharge(sessions, state)
    if sessions['wakeup'] is None:
        __missing_wakeup(sessions, state)
    __start_active(sessions,
                   state,
                   'DEVICE',
                   matches.groups()[0],
                   sessions['suspend'].start_cc)
    sessions['active'].start = sessions['suspend'].start
    sessions['active'].start_time = sessions['suspend'].start_time
    __cancel_suspend(sessions, state)
    return

def resumed_regex_hook(sessions, state, matches):
    if sessions['discharge'] is None and sessions['charge'] is not None:
        return
    elif sessions['discharge'] is None:
        __missing_discharge(sessions, state)
    result = int(matches.groups()[0])
    rtc_time = matches.groups()[1]
    start_cc = MIN_INT
    if sessions['suspend'] is not None:
        start_cc = sessions['suspend'].start_cc
    # Last suspend session can be closed here
    if sessions['wakeup'] is None:
        __missing_wakeup(sessions, state)
    if result != 0:
        # Warning! Warning! Suspend not cancelled, Active not started
        if sessions['suspend'] is not None:
            if CSV:
                __csv_suspend(sessions, state, 'freeze_abort')
            __cancel_suspend(sessions, state)
        if sessions['active'] is None:
            __start_active(sessions,
                           state,
                           'ABORT',
                           'UNKNOWN',
                           start_cc)
        return
    else:
        if sessions['suspend'] is not None:
            if CSV:
                __csv_suspend(sessions, state)
            __close_suspend(sessions, state)
        if sessions['active'] is None:
            # display wake_up might have happened before
            __start_active(sessions, state, 'BACKGROUND',
                           state['wakeup_source'],
                           start_cc
                           )
        else:
            if sessions['active'].reason == 'displayon':
                state['wakeup_source'] = UNKNOWN
        return

def active_wakelock_regex_hook(sessions, state, matches):
    state['active_wakelock'] = matches.groups()[0]
    return

def display_sleep_regex_hook(sessions, state, matches):
    state['display'] = 'OFF'
    if sessions['discharge']:
        if sessions['active'] and sessions['active'].reason != 'displayoff':
            s = sessions['active']
            if s.start_cc == MIN_INT:
                # We don't have any cost logging so just closing it
                __close_active(sessions, state)
            else:
                s.end = state['kernel_time_stamp']
                s.end_time = __current_time(state)
                sessions['last_active'] = s
        # Not likly sleep happens without any prior discharge/wakeup event
        __start_displayoff(sessions, state)
    return

def display_wakeup_regex_hook(sessions, state, matches):
    state['display'] = 'ON'
    if sessions['discharge']:
        if sessions['active'] and sessions['active'].reason != 'displayon':
            s = sessions['active']
            if s.start_cc == MIN_INT:
                # We don't have any cost logging so just closing it
                __close_active(sessions, state)
            else:
                s.end = state['kernel_time_stamp']
                s.end_time = __current_time(state)
                sessions['last_active'] = s
        if sessions['active'] is None or\
                sessions['active'].reason != 'displayon':
            __start_displayon(sessions, state)
    return

def wakeup_source_before_wakeuplock_regex_hook(sessions, state, matches):
    # A new wakeup can be started here
    # Suspend not closed yet because we don't know cost until resumed regex seen
    if sessions['charge'] is not None or sessions['discharge'] is None:
        __close_charge(sessions, state)
        __missing_discharge(sessions, state, matches)
    state['wakeup_source'] = matches.groups()[0]
    if sessions['wakeup'] is None:
        __start_wakeup(sessions, state, matches.groups()[0])
    if sessions['active'] is None:
        __start_active(sessions, state)
        sessions['active'].type = 'BACKGROUND'
        sessions['active'].reason = matches.groups()[0]
    return

def wakeup_wakelock_regex_hook(sessions, state, matches):
    # A new wakeup can be started here - if it's not created in previous func
    # Suspend not closed yet because we don't know cost until resumed regex seen
    if sessions['wakeup'] is None:
        if sessions['charge'] is not None or sessions['discharge'] is None:
            __close_charge(sessions, state)
            __missing_discharge(sessions, state, matches)
        __start_wakeup(sessions, state, matches.groups()[0])
    if sessions['active'] is None:
        __start_active(sessions, state)
        sessions['active'].type = 'BACKGROUND'
        sessions['active'].reason = matches.groups()[0]
    return

def wakeup_source_after_wakeuplock_regex_hook(sessions, state, matches):
    # A new wakeup can be started here - if it's not created in previous func
    # Suspend not closed yet because we don't know cost until resumed regex seen
    if sessions['charge'] is not None or sessions['discharge'] is None:
        __close_charge(sessions, state)
        __missing_discharge(sessions, state, matches)
    if sessions['active'] is None:
        __start_active(sessions, state)
        sessions['active'].type = 'BACKGROUND'
        sessions['active'] = matches.groups()[0]
    return

def suspend_coulomb_regex_hook(sessions, state, matches):
    # This is the first possible indicator for suspend start, but not in user
    # build. Here we can close last active session
    if sessions['charge'] is not None or sessions['discharge'] is None:
        __close_charge(sessions, state)
        __missing_discharge(sessions, state)
    if sessions['suspend'] is not None:
        __missing_log_warning(sessions,state, 'suspend')
        sessions['suspend'] = None
    if sessions['wakeup'] is None:
        __missing_wakeup(sessions, state)
    if sessions['active'] is None:
        __missing_log_warning(sessions,state, 'active')
        if CSV:
            __csv_active(sessions, state)
    else:
        if sessions['last_active']:
            __close_last_active(sessions, state, __cc(matches.groups()[0]))
        sessions['active'].end_cc = __cc(matches.groups()[0])
        sessions['active'].cost = __cost(sessions['active'])
        if CSV:
            __csv_active(sessions, state)
        __close_active(sessions, state)
    __start_suspend(sessions, state, __cc(matches.groups()[0]))
    return

def resume_coulomb_regex_hook(sessions, state, matches):
    if sessions['active'] and sessions['active'].type == 'BACKGROUND':
        sessions['active'].start_cc = __cc(matches.groups()[0])
    if sessions['suspend']:
        sessions['suspend'].end_cc = __cc(matches.groups()[0])
        sessions['suspend'].cost = __cost(sessions['suspend'])
    return

def longest_wakelock_regex_hook(sessions, state, matches):
    state['longest_wakelock_name'] = matches.groups()[0]
    state['longest_wakelock_len'] = float(matches.groups()[1])/1000000000
    add_onto_elem_in_dict(
        sessions['full'].blocker_stats,
        state['longest_wakelock_name'],
        1,
        state['longest_wakelock_len'],
        0,
        0,
        )
    return

def suspend_duration_regex_hook(sessions, state, matches):
    if sessions['suspend']:
        if len(matches.groups()) > 1:
            sessions['suspend'].rtc_only =\
                float(matches.groups()[0]) + float(matches.groups()[1])/1000
        else:
            sessions['suspend'].rtc_only = float(matches.groups()[0])/1000000000
    return

def display_sleep_coulomb_regex_hook(sessions, state, matches):
    if sessions['active'] and sessions['active'].reason == 'displayoff':
        sessions['active'].start_cc = __cc(matches.groups()[0])
    if sessions['last_active']:
        __close_last_active(sessions, state, __cc(matches.groups()[0]))

    return

def display_wakeup_coulomb_regex_hook(sessions, state, matches):
    if sessions['active'] and sessions['active'].reason == 'displayon':
        sessions['active'].start_cc = __cc(matches.groups()[0])
    if sessions['last_active']:
        __close_last_active(sessions, state, __cc(matches.groups()[0]))
    return

def __close_sessions(sessions, state):
    if sessions['active']:
        if CSV:
            __csv_active(sessions, state)
        __close_active(sessions, state)
    if sessions['wakeup']:
        __close_wakeup(sessions, state)
    if sessions['suspend']:
        __close_suspend(sessions, state)
    if sessions['discharge']:
        __close_discharge(sessions, state)
    return

def charging_regex_hook(sessions, state, matches):
    if sessions['charge'] is None:
        __close_sessions(sessions, state)
        __start_charge(sessions, state)
    return

def discharging_regex_hook(sessions, state, matches):
    # discharge message might print several times
    if sessions['discharge'] is not None:
        __missing_log_warning(sessions, state, 'un discharge')
        return
    else:
        if sessions['charge'] is None:
            # boot-up case
            __missing_log_warning(sessions, state, 'charge')
            sessions['full'].usb_time +=\
                __current_time(state) - sessions['full'].start_time
        else:
            __csv_suspend(sessions, state, 'charger')
            sessions['full'].usb_time +=\
                __current_time(state) - sessions['charge'].start_time
            sessions['charge'] = None
        __start_discharge(sessions, state)
        __start_wakeup(sessions, state)
    if sessions['wakeup'] is None:
        __error_missing_log(sessions, state, 'wakeup')
    if state['display'] == 'ON':
        __start_displayon(sessions, state)
    else:
        __start_displayoff(sessions, state)
    return

def deep_sleep_regex_hook(sessions, state, matches):
    __close_wakeup(sessions, state)
    return

def cpu1_on_regex_hook(sessions, state, matches):
    state['cpu1_on'] = __current_time(state)
    return

def cpu1_off_regex_hook(sessions, state, matches):
    if state['cpu1_on'] == -2.0:
        state['cpu1_on'] = sessions['full'].start_time
    elif state['cpu1_on'] == -1.0:
        return
    sessions['full'].cpu1_time +=\
        __current_time(state) - state['cpu1_on']
    state['cpu1_on'] = -1.0
    return

def __debug_print_all(sessions, state):
    sys.stderr.write("sessions are:%s"%os.linesep)
    for key in sessions.keys():
        if sessions[key]:
            sys.stderr.write("---%s---%s"%(key, os.linesep))
            sessions[key].debug_print()
        else:
            sys.stderr.write("---%s--- is None%s"%(key, os.linesep))
    sys.stderr.write("state is:%s"%os.linesep)
    for k in state.keys():
        sys.stderr.write("%s is %s%s"%(k, state[k], os.linesep))
    return

def roll(fobj_in, fobj_out):
    cur_state = __init_cur(fobj_out)
    if fobj_out:
        fobj_out.write(
            "ActiveDuration,ActiveCurrent,SuspendEnter,SuspendDuration,SuspendExit,SuspendStatus,SuspendCurrent,WakeupSource\n")
    live_sessions = dict()
    live_sessions['full'] = None
    live_sessions['discharge'] = None
    live_sessions['charge'] = None
    live_sessions['active'] = None
    live_sessions['suspend'] = None
    live_sessions['wakeup'] = None # started from wakeup_wakelock, ended 
    live_sessions['last_active'] = None
    try:
        l = fobj_in.readline()
        while (len(l)):
            t,b = time_and_body(l)
            if t is not None:
                cur_state['kernel_time_stamp'] = t
                if not live_sessions['full']:
                    live_sessions['full'] = FullLogSession(
                        start = t,
                        start_time = __current_time(cur_state))
                for k in REGEX.keys():
                    r,f = REGEX[k]
                    m = r.match(b)
                    if m is not None:
                        if f in globals().keys():
                            hook = globals()[f]
                            hook(live_sessions, cur_state, m)
            l = fobj_in.readline()
        if live_sessions['charge']:
            live_sessions['full'].usb_time +=\
                __current_time(cur_state) - live_sessions['charge'].start_time
        if cur_state['cpu1_on'] > 0:
            live_sessions['full'].cpu1_time +=\
                __current_time(cur_state) - cur_state['cpu1_on']
        # close all live sessions
        __close_sessions(live_sessions, cur_state)
        live_sessions['full'].end = cur_state['kernel_time_stamp']
        live_sessions['full'].end_time = __current_time(cur_state)
        live_sessions['full'].duration = __duration(live_sessions['full'])
    except:
        __debug_print_all(live_sessions, cur_state)
        raise
    return live_sessions['full']

TAB_WIDTH = 8
TAB_2_WIDTH = 24

def table(tab_n, header, values, widths=None):
    line = ''
    sep = ''
    col_n = len(header)
    for i in range(tab_n):
        line += '\t'
        sep += '\t'
    for i in range(col_n):
        w = TAB_2_WIDTH
        if widths:
            w = widths[i]
        line += header[i]
        sep += '_'*w
        padding = w - len(header[i])
        if padding > 0:
            j = padding/TAB_WIDTH + 1
            for n in range(j):
                line += '\t'
    print sep
    print line
    for rol in values:
        line = ''
        for i in range(tab_n):
            line += '\t'
        for col in rol:
            cell = '%s'%col
            line += cell
            w = TAB_2_WIDTH
            if widths:
                w = widths[i]
            padding = w - len(cell)
            if padding > 0:
                j = padding/TAB_WIDTH + 1
                for n in range(j):
                    line += '\t'
        print line            
    print sep
    print ''

def sum_table(tab_n, sum_dict, width = TAB_2_WIDTH):
    header = ['name','count','duration(seconds)','cost(mAh)']
    cells = list()
    for s in sum_dict.keys():
        i = sum_dict[s]
        cells.append([s, '%d'%i.count, '%.2f'%i.duration, '%.2f'%i.cost])
    table(tab_n, header, cells, width)
    return

def top_table(tab_n, top_list,
              header=['name','count','duration(seconds)','cost(mAh)'],
              fields=['name','count','duration','cost'],
              width = [TAB_2_WIDTH]*4,
              names = None
              ):
    cells = list()
    for i in top_list:
        line = list()
        for f in fields:
            if names:
                if f in names.keys():
                    t = names[f]
                    raw = getattr(i, f)
                    if raw in t.keys():
                        line.append('%s'%t[raw])
                    else:
                        line.append('%s'%raw)
                else:
                    line.append('%s'%getattr(i, f))
            else:
                line.append('%s'%getattr(i, f))
        cells.append(line)
    table(tab_n, header, cells, width)
    return

def __duration_cost_current(s):
    c = 0.0
    cd = 0.0
    d = s.duration
    if s.cost_duration != 0:
        c = s.cost
        cd = c*3600/s.cost_duration
    return (d,c,cd)
def print_summary(full):
    if full.duration == 0:
        print "Log file is invalid!"
        return
    print 'Total log time:\t\t\t%s'%(full.duration)
    session = full
    if LAST:
        print os.linesep+'There are following discharge cycles logged:'
        top_table(2, full.discharge_sessions,\
                      ['Duration(seconds)','Start','End'],\
                      ['duration','start','end'],\
                      )
        print 'Following results are for the last discharge cycle:'
        session = full.discharge_sessions.pop()
    else:
        print 'Total CPU1 up time:\t\t%0.2f\t(%0.2f%%)'%(
            session.cpu1_time,
            session.cpu1_time*100/session.duration
            )
    (d, c, cd) = __duration_cost_current(session.suspend_sum)
    print 'Total suspend time:\t\t%0.2f\t(%0.2f%%) %0.2fmA %0.2fmAh'%(
            d,
            d*100/session.duration,
            cd,
            c)
    print 'Total successful suspend count:\t\t%d'%(session.suspend_sum.count)
    print 'Total Active time:'
    print '\tTotal USB connected time:\t%0.2f\t(%0.2f%%)'%(
        session.usb_time,
        session.usb_time*100/session.duration)
    (d, c, cd) = __duration_cost_current(session.display_sum)
    print '\tTotal display on time:\t\t%0.2f\t(%0.2f%%) %0.2fmA %0.2fmAh'%(
            d,
            d*100/session.duration,
            cd,
            c)
    (d, c, cd) = __duration_cost_current(session.active_sum)
    print '\tTotal display off (active) time:%0.2f\t(%0.2f%%) %0.2fmA %0.2fmAh'%(
                d,
                d*100/session.duration,
                cd,
                c)
    if sys.stdout.isatty():
        print '%sPress q<RET> to quit, any other key and <RET> for more deteils...'%os.linesep
        i = sys.stdin.readline()
        if i[0] == 'q':
            return
    print 'Reasons Keeping Phone active'
    cells = list()
    tops = dict()
    for n,d in [('From Suspend', session.active_stats['BACKGROUND']),
                ('Freezing Abort', session.active_stats['ABORT']),
                ('Device Failure', session.active_stats['DEVICE']),
                ('User Operation', session.active_stats['DISPLAYOFF']),
                ]:
        tops[n] = Top('count')
        count = 0
        time = 0.0
        cost = 0.0
        for i in d.keys():
            tops[n].insert(d[i])
            count += d[i].count
            time += d[i].duration
            cost += d[i].cost
        cells.append([n,'%d'%count,'%.2f'%time, '%.2f'%cost])
    table(1, ['Reason', 'Count', 'Duration(seconds)', 'Cost(mAh)'], cells)
    print '\tTop Wakeup Sources by Count'
    t = Top('count')
    t.select(session.active_stats['BACKGROUND'].values())
    top_table(2, t.list)
    print '\tTop Freezing Abort by Count'
    t = Top('count')
    t.select(session.active_stats['ABORT'].values())
    top_table(2, t.list)
    print '\tTop Device Failure by Count'
    t = Top('duration')
    t.select(session.active_stats['DEVICE'].values())
    top_table(2, t.list)
    if VERBOSE == False:
        return
    print '\tLongest Display Session'
    top_table(2, session.tops['duration_displayon'].list,\
                  ['duration(seconds)','start','end','cost(mAh)'],\
                  ['duration','start','end','cost']\
                  )
    print '=============================='
    print 'Hot Spots'
    print '=============================='
    print 'Top Wakeup Sources by Duration'
    t = Top('duration')
    t.select(session.active_stats['BACKGROUND'].values())
    top_table(1, t.list)
    print 'Top Wakeup Sources by Cost'
    t = Top('cost')
    t.select(session.active_stats['BACKGROUND'].values())
    top_table(1, t.list)
    print 'Top Freezing Abort by Duration'
    t = Top('duration')
    t.select(session.active_stats['ABORT'].values())
    top_table(1, t.list)
    print 'Top Freezing Abort by Cost'
    t = Top('cost')
    t.select(session.active_stats['ABORT'].values())
    top_table(1, t.list)
    print 'Top Device Failure by Duration'
    t = Top('count')
    t.select(session.active_stats['DEVICE'].values())
    top_table(1, t.list)
    print 'Top Device Failure by Cost'
    t = Top('count')
    t.select(session.active_stats['DEVICE'].values())
    top_table(1, t.list)
    print 'Top Blocking Wakelocks by Count'
    t = Top('count')
    t.select(session.blocker_stats.values())
    top_table(1, t.list)
    print 'Top Blocking Wakelocks by Duration'
    t = Top('count')
    t.select(session.blocker_stats.values())
    top_table(1, t.list)
    print 'Top Blocking Wakelocks by Cost'
    t = Top('count')
    t.select(session.blocker_stats.values())
    top_table(1, t.list)

    print '=============================='
    print 'Hot Areas'
    print '=============================='

    print 'Longest Awoken Sessions'
    top_table(2, session.tops['duration_awoken'].list,\
                  ['duration(seconds)','start','end','cost(mAh)'],\
                  ['duration','start','end','cost',]\
                  )
    print 'Most Expensive Awoken Sessions'
    top_table(2, session.tops['cost_awoken'].list,\
                  ['cost','start','end','duration'],\
                  ['cost','start','end','duration'],\
                  )                  
    print 'Longest Display-off Active Sessions'
    top_table(2, session.tops['duration_active'].list,\
                  ['duration','start','end','cost'],\
                  ['duration','start','end','cost',]\
                  )
    print 'Most Expensive Display-off Active Sessions'
    top_table(2, session.tops['cost_active'].list,\
                  ['cost','start','end','duration'],\
                  ['cost','start','end','duration'],\
                  )
    print 'Longest Display-On Sessions'
    top_table(2, session.tops['duration_displayon'].list,\
                  ['duration','start','end','cost'],\
                  ['duration','start','end','cost',]\
                  )
    print 'Most Expensive Display-On Sessions'
    top_table(2, session.tops['cost_displayon'].list,\
                  ['duration','start','end','cost'],\
                  ['duration','start','end','cost',]\
                  )
    return

def append_regex(platxml, tag, func, array):
    elem = platxml.getElementsByTagName(tag)
    if elem:
        array[tag] = (re.compile(elem[0].childNodes[0].data), func)

INTERRUPTS = dict()
if __name__ == "__main__":
    current_dir = os.getcwd()
    sys.stderr.write(SOFTWARE_NAME+' '+LAST_UPDATE+os.linesep)
    sys.stderr.write(AUTHOR+os.linesep)
    print "----"
    if len(sys.argv) < 2:
        __usage()
        sys.exit(1)

    parser = OptionParser()
    parser.add_option("-p", "--plat", dest="plat")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      default=VERBOSE,
                      help="")
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                      default=DEBUG,
                      help="")
    parser.add_option("-l", "--last", action="store_true", dest="last",
                      default=LAST,
                      help="")
    parser.add_option("-n", "--nocsv", action="store_false", dest='csv',
                      default=CSV,
                      help="")
    (options, args) = parser.parse_args(sys.argv)
    VERBOSE = options.verbose
    DEBUG = options.debug
    CSV = options.csv
    LAST = options.last
    if VERBOSE:
        LAST = True
    objfile = args[1]
    __debug_print("DEBUG message is on!")
    plat = 'default'
    platfile = os.path.dirname(os.path.realpath(__file__))+os.sep+plat+'.xml'
    if options.plat:
        plat = options.plat
        platfile = os.path.dirname(os.path.realpath(__file__))+os.sep+plat+'.xml'
        if not os.path.isfile(platfile):
            platfile = current_dir+os.sep+plat+'.xml'
    if not os.path.isfile(platfile):
        __error_print("platform [%s] is not fully supported yet"%plat)
        
        __usage()
        sys.stderr.write(
            '%sPress q<RET> to quit, any other key and <RET> to continue...'
            %os.linesep)
        i = sys.stdin.readline()
        if i[0] == 'q':
            sys.exit(1)
    try:
        platxml = minidom.parseString(open(platfile).read())
        for i in BSP_REGEX.keys():
            append_regex(platxml, i, BSP_REGEX[i], REGEX)
        interrupts = platxml.getElementsByTagName('interrupts')[0]
        irqs = interrupts.getElementsByTagName('irq')
        for i in irqs:
            INTERRUPTS[i.getAttribute('number')] = i.getAttribute('name')
    except:
        pass

    fobj_in = None
    fobj_out = None
    try:
        fobj_in = open(objfile, 'r')
        if CSV:
            fobj_out = open(objfile+'.csv', 'w')
    except Exception as e:
        __error_print('Opening input or output file:%s%s'%
                      (os.linesep,e))
        if fobj_in:
            fobj_in.close()
        sys.exit(1)

    f = roll(fobj_in, fobj_out)
    if CSV:
        fobj_out.close()
    fobj_in.close()
    print_summary(f)
# Main Sections Ends
################################################################################
