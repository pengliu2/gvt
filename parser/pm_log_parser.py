import string,os,re,sys
from optparse import OptionParser
from xml.dom import minidom,Node

TOP = 5
SOFTWARE_NAME = 'log parser'
AUTHOR = 'Peng Liu - <a22543@motorola.com>'
LAST_UPDATE = 'JUL 12, 2012'

################################################################################
UNKNOWN = 'UNKNOWN'
TIME_UNIT = 1000000000
VERBOSE = False
# Utility functions
DEBUG = False
TECH = False
def __debug_print(msg):
    if DEBUG is True:
        sys.stderr.write('DEBUG: %s'%msg+os.linesep)
quiet = False
def __warning_print(msg):
    if TECH or VERBOSE or DEBUG:
        sys.stderr.write('WARNING: %s'%msg+os.linesep)
def __error_print(msg):
    if quiet is False:
        sys.stderr.write('ERROR: %s'%msg+os.linesep)

def __usage():
    sys.stderr.write('USAGE; python -u pm_log_parser.py -p <platform> <dmesg.txt>'+os.linesep)
    sys.stderr.write('Summary statistics will be printed to stdout '+
                     'and <dmesg.txt>.csv has details.'+os.linesep)
    sys.exit(1)

def __current_time(c):
    return float(c['kernel_time_stamp']) + KERNEL_TIME_LIMIT *\
        c['kernel_time_wrapup_counter']

def __duration(s):
    return s.end_time - s.start_time + s.rtc_only

def __cost_capacity(s):
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

def __cost(s, style = 'CC'):
    cost_function_name = '__cost_%s'%style
    if cost_function_name in globals().keys():
        cost_function = globals()[cost_function_name]
        return cost_function(s)

def __add_onto_elem_in_dict(d, k, number=0, duration=0, cost=0):
    if k not in d.keys():
        d[k] = Sum(k)
    d[k].update(number, duration, cost)
################################################################################
TOP = 5
class Sum(object):
    def __init__(self, name='', duration=0.0, cost=0.0, count=0):
        self.count = count
        self.duration = duration
        self.cost = cost
        self.name = name
    def count_inc(self):
        self.count += 1
    def duration_add(self, d):
        self.duration += d
    def cost_add(self, c):
        self.cost += c
    def update(self, count, duration, cost):
        self.count += count
        self.duration += duration
        self.cost += cost
    def add(self, duration, cost):
        self.count += 1
        self.duration += duration
        self.cost += cost

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

suspend_result = {
    'UNKNOWN': -1,
    'SUCCESS': 0,
    'ABORTED': 1,
    'DEVICE': 2,
    'DISPLAY': 3,
    'DISPLAYOFF':4,
    'BOOTUP': 999
    }

class Session(object):
    def __init__(self,
                 start=UNKNOWN,
                 start_time=0,
                 end=UNKNOWN,
                 duration=0.0,
                 cost=0.0,
                 typ=UNKNOWN,
                 reason = UNKNOWN,
                 start_cc = 0.0
                 ):
        self.start = start
        self.end = end
        self.start_cc = start_cc
        self.end_cc = 0.0
        self.cost = cost
        self.duration = duration
        self.type = typ
        self.reason = reason
        self.start_time = start_time
        self.end_time = -1.0
        self.rtc_only = 0.0

    def debug_print(self):
        print ("start = %s"%self.start)
        print ("end = %s"%self.end)
        print ("type = %s"%self.type)
        print ("reason = %s"%self.reason)

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
        self.tops = dict()

        self.tops['cost_displayon'] = Top('cost')
        self.tops['duration_displayon'] = Top('duration')

        self.tops['cost_active'] = Top('cost')
        self.tops['duration_active'] = Top('duration')

        self.tops['cost_awoken'] = Top('cost')
        self.tops['duration_awoken'] = Top('duration')

        if not TECH and not VERBOSE:
            self.usb_time = 0.0
            self.cpu1_time = 0.0
            self.full_stats = dict()
            self.full_stats['BACKGROUND'] = dict()
            self.full_stats['ABORT'] = dict()
            self.full_stats['DEVICE'] = dict()
            self.full_stats['DISPLAY'] = dict()
            self.full_stats['DISPLAYOFF'] = dict()
            self.full_stats['LONGEST'] = dict()
            self.active_sum = Sum()
            self.suspend_sum = Sum()
            self.head = 0.0
            self.tail = 0.0

class AwokenSum(Sum):
    def __init__(self):
        super(AwokenSum, self).__init__()

        self.active_stats = dict()
        self.active_stats['BACKGROUND'] = dict()
        self.active_stats['ABORT'] = dict()
        self.active_stats['DEVICE'] = dict()
        self.active_stats['DISPLAY'] = dict()
        self.active_stats['DISPLAYOFF'] = dict()

        self.blocker_stats = dict()

class DischargeSession(Session):
    def __init__(self,
                 start=UNKNOWN,
                 start_time=0,
                 end=UNKNOWN,
                 duration=0.0,
                 cost=0.0,
                 typ=UNKNOWN,
                 reason = UNKNOWN,
                 start_cc = 0.0
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
        self.awoken_sum = AwokenSum()
        self.suspend_sum = Sum()

# Not used yet
################################################################################

def __init_cur():
    cur_state = dict()

    cur_state['state'] = UNKNOWN

    # This is for the last resume from successful suspend
    cur_state['resume_time'] = -1.0
    cur_state['resume_ts'] = UNKNOWN
    cur_state['resume_coulomb'] = sys.maxint
    # This is for the last suspend attempt, no matter if successful or not
    cur_state['susp_kicked_time'] = -1.0
    cur_state['susp_kicked_ts'] = 'UNKNOWN'
    # This is for the nearest suspend attempt
    cur_state['suspend_result'] = suspend_result['SUCCESS']
    cur_state['susp_kicked_coulomb'] = sys.maxint
    cur_state['suspend_duration'] = 0
    # This is for the nearest activating
    cur_state['activated_coulomb'] = sys.maxint
    cur_state['activated_time'] = -1.0
    cur_state['activated_ts'] = UNKNOWN
    # This is for tne nearest resume
    cur_state['active_wakelock'] = UNKNOWN
    cur_state['failed_device'] = UNKNOWN
    cur_state['wakeup_source'] = UNKNOWN
    cur_state['active_type'] = 'UNKNOWN'
    cur_state['active_reason'] = UNKNOWN

    cur_state['kernel_time_stamp'] = ''
    cur_state['kernel_time_wrapup_counter'] = 0
    cur_state['longest_wakelock_name'] = None
    cur_state['longest_wakelock_len'] = 0

    cur_state['display'] = UNKNOWN

    cur_state['wakeup_time'] = 0.0
    cur_state['sleep_time'] = 0.0
    cur_state['wakeup_ts'] = UNKNOWN
    cur_state['sleep_ts'] = UNKNOWN
    cur_state['sleep_coulomb'] = sys.maxint
    cur_state['wakeup_coulomb'] = sys.maxint

    cur_state['gptimer_stop_time'] = 0.0

    if not TECH and not VERBOSE:
        cur_state['charging_start'] = -2.0
        cur_state['cpu1_on'] = -2.0

    return cur_state

################################################################################
# Log Processing Section Starts
KERNEL_TIME_LIMIT = 131072.0
KERNEL_TIME_STAMP =\
    re.compile('^<\d>\[ *(\d+)\.(\d{6})[^\]]*\] (.*)')
LOGCAT_TIME_STAMP =\
    re.compile('^(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3}) (.*)')
def time_and_body(line):
    n = KERNEL_TIME_STAMP.match(line)
    if n is None:
        return (None,None)
    return (n.groups()[0]+'.'+n.groups()[1],n.groups()[2])
# Log Processing Section Starts
################################################################################

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
        (re.compile('suspend: exit suspend, ret = 0 \((\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{9}) UTC\)'),
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
    'cpu1_off': 'cpu1_off',
    'cpu1_on': 'cpu1_on',
    }

def __missing_log_warning(s,c,e):
    __warning_print('%s session state is abnormal'%e)
    __warning_print('There might be log missing before %s'%c['kernel_time_stamp'])
    if DEBUG:
        __debug_print_all(s,c)
    return

def __missing_discharge(sessions, state, matches = None):
    __missing_log_warning(sessions, state, 'discharge')
    sessions['discharge'] = DischargeSession(
        start = sessions['full'].start,
        start_time = sessions['full'].start_time
        )
    return

def __missing_wakeup(sessions, state, matches = None):
    __missing_log_warning(sessions, state, 'wakeup')
    sessions['wakeup'] = Session(
        start = sessions['full'].start,
        start_time = sessions['full'].start_time
        )
    return

def __missing_suspend(sessions, state, matches = None):
    __missing_log_warning(sessions, state,'suspend')
    sessions['suspend'] = Session(
        start = sessions['full'].start,
        start_time = sessions['full'].start_time
        )
    return

def __start_suspend(sessions, state, matches = None):
    if sessions['suspend'] is None:
        sessions['suspend'] = Session(
            start=state['kernel_time_stamp'],
            start_time=__current_time(state)
            )
        if matches:
            if len(matches.groups()):
                sessions['suspend'].start_cc = float(matches.groups()[0])/1000
    return

def __close_suspend(sessions, state, matches = None):
    if sessions['suspend'] is not None:
        s = sessions['suspend']
        s.end = state['kernel_time_stamp']
        s.end_time = __current_time(state)
        s.duration = __duration(s) + state['suspend_duration']
        if sessions['discharge']:
            sessions['discharge'].suspend_sum.add(s.duration, s.cost)
            sessions['discharge'].rtc_only += state['suspend_duration']
        sessions['suspend'] = None
    return


def __start_active(sessions, state, matches = None):
    if sessions['active'] is None:
        sessions['active'] = Session(
            start=state['kernel_time_stamp'],
            start_time=__current_time(state),
            typ=state['active_type'],
            reason=UNKNOWN
            )
    return

def __cancel_suspend(sessions, state, matches = None):
    __start_active(sessions, state, matches)
    sessions['active'].start_cc = sessions['suspend'].start_cc
    sessions['suspend'] = None
    return
    
def __close_active(sessions, state, matches = None):
    if sessions['active'] is not None:
        s = sessions['active']
        if s.type == 'DISPLAY' or s.type == 'DISPLAYOFF':
            __close_last_active(sessions, state, matches)

        s.end = state['kernel_time_stamp']
        s.end_time = __current_time(state)
        s.duration = __duration(s)
        if sessions['discharge']:
            __add_onto_elem_in_dict(
                sessions['discharge'].awoken_sum.active_stats[s.type],
                s.reason,
                1,
                s.duration,
                s.cost
                )
        if not TECH and not VERBOSE:
            __add_onto_elem_in_dict(
                sessions['full'].full_stats[s.type],
                s.reason,
                1,
                s.duration,
                s.cost
                )
            if s.type != 'DISPLAY':
                sessions['full'].active_sum.add(s.duration, s.cost)
            sessions['full'].tops['cost_active'].insert(s)
            sessions['full'].tops['duration_active'].insert(s)
        if sessions['wakeup']:
            sessions['wakeup'].cost += sessions['active'].cost
        sessions['active'] = None
    return

def __start_charge(sessions, state, matches = None):
    if sessions['charge'] is None:
        sessions['charge'] = Session(
            start = state['kernel_time_stamp'],
            start_time = __current_time(state)
            )
    return

def __close_charge(sessions, state, matches = None):
    sessions['charge'] = None
    return

def __start_discharge(sessions, state, matches = None):
    if sessions['discharge'] is None:
        sessions['discharge'] = DischargeSession(
            start = state['kernel_time_stamp'],
            start_time = __current_time(state)
            )
    return

def __close_discharge(sessions, state, matches = None):
    if sessions['discharge'] is not None:
        s = sessions['discharge']
        s.end = state['kernel_time_stamp']
        s.end_time = __current_time(state)
        s.duration = __duration(s) + s.rtc_only
        if not TECH and not VERBOSE:
            sessions['full'].suspend_sum.update(s.suspend_sum.count,
                                                s.suspend_sum.duration,
                                                s.suspend_sum.cost)
        sessions['full'].discharge_sessions.append(s)
        sessions['full'].rtc_only += s.rtc_only
        sessions['discharge'] = None

def __start_wakeup(sessions, state, matches = None):
    if sessions['wakeup'] is None:
        sessions['wakeup'] = Session(
            start = state['kernel_time_stamp'],
            start_time = __current_time(state)
            )
        if matches and matches.groups():
            sessions['wakeup'].reason = matches.groups()[0]
    return

def __close_wakeup(sessions, state, matches = None):
    if sessions['wakeup'] is not None:
        s = sessions['wakeup']
        if s.end_time < 0:
            s.end = state['kernel_time_stamp']
            s.end_time = __current_time(state)
            s.duration = __duration(s)
        sessions['full'].tops['cost_awoken'].insert(s)
        sessions['full'].tops['duration_awoken'].insert(s)
        if sessions['discharge']:
            sessions['discharge'].awoken_sum.add(s.duration, s.cost)
    sessions['wakeup'] = None

def __start_displayon(sessions, state, matches = None):
    sessions['active'] = Session(
        start = state['kernel_time_stamp'],
        start_time = __current_time(state),
        typ = 'DISPLAY',
        reason = 'displayon'
        )
    return

def __close_last_active(sessions, state, matches = None):
    if sessions['last_active']:
        s = sessions['last_active']
        if matches:
            if len(matches.groups()):
                s.end_cc = float(matches.groups()[0])/1000
        s.cost = __cost(s)
        s.duration = __duration(s)
        if sessions['discharge']:
            __add_onto_elem_in_dict(
                sessions['discharge'].awoken_sum.active_stats[s.type],
                s.reason,
                1,
                s.duration,
                s.cost
                )
        sessions['full'].tops['cost_active'].insert(s)
        sessions['full'].tops['duration_active'].insert(s)
        if s.reason == 'displayon':
            sessions['full'].tops['cost_displayon'].insert(s)
            sessions['full'].tops['duration_displayon'].insert(s)
            if not TECH and not VERBOSE:
                __add_onto_elem_in_dict(
                    sessions['full'].full_stats['DISPLAY'],
                    s.reason,
                    1,
                    s.duration,
                    s.cost
                    )
        else:
            if not TECH and not VERBOSE:
                sessions['full'].active_sum.add(s.duration, s.cost)
                __add_onto_elem_in_dict(
                    sessions['full'].full_stats[s.type],
                    s.reason,
                    1,
                    s.duration,
                    s.cost
                    )


        if sessions['wakeup']:
            sessions['wakeup'].cost += s.cost
        sessions['last_active'] = None
    return

def __start_displayoff(sessions, state, matches = None):
    sessions['active'] = Session(
        start = state['kernel_time_stamp'],
        start_time = __current_time(state),
        typ = 'DISPLAYOFF',
        reason = 'displayoff'
        )
    return

def booting_regex_hook(sessions, state, matches):
    __start_discharge(sessions, state, matches)
    __start_wakeup(sessions, state)
    __start_active(sessions, state, matches)
    sessions['active'].type = 'BACKGROUND'
    sessions['active'].reason = 'bootup'
    return

def freezing_regex_hook(sessions, state, matches):
    # If last active session hasn't been closed, close it here
    if sessions['charge'] is not None or sessions['discharge'] is None:
        __close_charge(sessions, state, matches)
        __missing_discharge(sessions, state, matches)
    if sessions['wakeup'] is None:
        __missing_wakeup(sessions, state, matches)
    if sessions['active'] is not None:
        __close_active(sessions, state, matches)
    __start_suspend(sessions, state, matches)
    return

def aborted_regex_hook(sessions, state, matches):
    # Don't have to check other sessions because this line has been processed by freezing_regex_hook
    # Starts next active
    __cancel_suspend(sessions, state, matches)
    sessions['active'].type = 'ABORT'
    sessions['active'].reason = state['active_wakelock']
    return

def failed_device_regex_hook(sessions, state, matches):
    # Starts next active
    if sessions['charge'] is not None or sessions['discharge'] is None:
        __close_charge(sessions, state, matches)
        __missing_discharge(sessions, state, matches)
    if sessions['wakeup'] is None:
        __missing_wakeup(sessions, state, matches)
    if sessions['active'] is not None:
        __missing_log_warning(sessions, state, 'active')
        sessions['active'] = None
    state['active_type'] = 'DEVICE'
    __cancel_suspend(sessions, state, matches)
    sessions['active'].reason = matches.groups()[0]
    return

def resumed_regex_hook(sessions, state, matches):
    # Last suspend session can be closed here
    if sessions['charge'] is not None or sessions['discharge'] is None:
        __close_charge(sessions, state, matches)
        __missing_discharge(sessions, state, matches)
    if sessions['suspend'] is not None:
        __close_suspend(sessions, state, matches)
    else:
        __missing_log_warning(sessions, state, 'suspend')
    if sessions['active'] is None:
        # display wake_up might have happened before
        __start_active(sessions, state, matches)
        sessions['active'].start_cc = state['resume_coulomb']
        sessions['active'].type = 'BACKGROUND'
        sessions['active'].reason = state['wakeup_source']
    elif sessions['active'].reason == 'displayon':
        if not TECH and not VERBOSE:
            __add_onto_elem_in_dict(
                sessions['full'].full_stats['BACKGROUND'],
                state['wakeup_source'],
                1,
                0,
                0,
                )
    state['wakeup_source'] = UNKNOWN
    return

def active_wakelock_regex_hook(sessions, state, matches):
    state['active_wakelock'] = matches.groups()[0]
    return

def display_sleep_regex_hook(sessions, state, matches):
    state['display'] = 'OFF'
    if sessions['discharge']:
        if sessions['last_active']:
            __close_last_active(sessions, state, matches)
        if sessions['active'] is not None and sessions['active'].reason != 'displayoff':
            sessions['last_active'] = sessions['active']
            sessions['last_active'].end = state['kernel_time_stamp']
            sessions['last_active'].end_time = __current_time(state)
        __start_displayoff(sessions, state, matches)
    return

def display_wakeup_regex_hook(sessions, state, matches):
    state['display'] = 'ON'
    if sessions['discharge']:
        if sessions['last_active']:
            __close_last_active(sessions, state, matches)
        if sessions['active'] and sessions['active'].reason != 'displayon':
            sessions['last_active'] = sessions['active']
            sessions['last_active'].end = state['kernel_time_stamp']
            sessions['last_active'].end_time = __current_time(state)
        if sessions['active'] is None or\
                sessions['active'].reason != 'displayon':
            __start_displayon(sessions, state, matches)
    return

def wakeup_source_regex_hook(sessions, state, matches):
    # A new wakeup can be started here
    # Suspend not closed yet because we don't know cost
    if sessions['charge'] is not None or sessions['discharge'] is None:
        __close_charge(sessions, state, matches)
        __missing_discharge(sessions, state, matches)
    if sessions['wakeup'] is not None:
        sessions['wakeup'] = None
    __start_wakeup(sessions, state, matches)
    state['wakeup_source'] = matches.groups()[0]
    return

def wakeup_source_before_wakeuplock_regex_hook(sessions, state, matches):
    # A new wakeup can be started here
    # Suspend not closed yet because we don't know cost
    if sessions['charge'] is not None or sessions['discharge'] is None:
        __close_charge(sessions, state, matches)
        __missing_discharge(sessions, state, matches)
    state['wakeup_source'] = matches.groups()[0]
    if sessions['active'] is None:
        __start_active(sessions, state, matches)
        sessions['active'].type = 'BACKGROUND'
        sessions['active'].reason = matches.groups()[0]
    return

def wakeup_wakelock_regex_hook(sessions, state, matches):
    if sessions['wakeup'] is None:
        if sessions['charge'] is not None or sessions['discharge'] is None:
            __close_charge(sessions, state, matches)
            __missing_discharge(sessions, state, matches)
        __start_wakeup(sessions, state, matches)
    if sessions['active'] is None:
        __start_active(sessions, state, matches)
        sessions['active'].type = 'BACKGROUND'
        sessions['active'].reason = matches.groups()[0]
    return

def wakeup_source_after_wakeuplock_regex_hook(sessions, state, matches):
    # A new wakeup can be started here
    # Suspend not closed yet because we don't know cost
    if sessions['charge'] is not None or sessions['discharge'] is None:
        __close_charge(sessions, state, matches)
        __missing_discharge(sessions, state, matches)
    if sessions['active'] is None:
        __start_active(sessions, state, matches)
        sessions['active'].type = 'BACKGROUND'
        sessions['active'] = matches.groups()[0]
    return

def suspend_coulomb_regex_hook(sessions, state, matches):
    # This is the first possible indicator for suspend start, but not in user build
    # Here we can close last active session
    if sessions['charge'] is not None or sessions['discharge'] is None:
        __close_charge(sessions, state, matches)
        __missing_discharge(sessions, state, matches)
    if sessions['suspend'] is not None:
        __missing_log_warning(sessions,state, 'suspend')
        sessions['suspend'] = None
    if sessions['wakeup'] is None:
        __missing_wakeup(sessions, state, matches)
    if sessions['active'] is None:
        __missing_log_warning(sessions,state, 'active')
    else:
        sessions['active'].end_cc = float(matches.groups()[0])/1000
        sessions['active'].cost = __cost(sessions['active'])
        __close_active(sessions, state, matches)
    __start_suspend(sessions, state, matches)
    return

def resume_coulomb_regex_hook(sessions, state, matches):
    if sessions['active'] and sessions['active'].type == 'BACKGROUND':
        sessions['active'].start_cc = float(matches.groups()[0])/1000
    if sessions['suspend']:
        sessions['suspend'].end_cc = float(matches.groups()[0])/1000
        sessions['suspend'].cost = __cost(sessions['suspend'])
    state['resume_coulomb'] = float(matches.groups()[0])/1000
    return

def longest_wakelock_regex_hook(sessions, state, matches):
    state['longest_wakelock_name'] = matches.groups()[0]
    state['longest_wakelock_len'] = float(matches.groups()[1])/1000000000
    __add_onto_elem_in_dict(
        sessions['full'].full_stats['LONGEST'],
        state['longest_wakelock_name'],
        1,
        state['longest_wakelock_len'],
        0,
        )
    return

def suspend_duration_regex_hook(sessions, state, matches):
    state['suspend_duration'] = float(matches.groups()[0])/1000000000
    return

def display_sleep_coulomb_regex_hook(sessions, state, matches):
    if sessions['active'] and sessions['active'].reason == 'displayoff':
        sessions['active'].start_cc = float(matches.groups()[0])/1000
    if sessions['last_active']:
        sessions['last_active'].end_cc = float(matches.groups()[0])/1000
    return

def display_wakeup_coulomb_regex_hook(sessions, state, matches):
    if sessions['active'] and sessions['active'].reason == 'displayon':
        sessions['active'].start_cc = float(matches.groups()[0])/1000
    if sessions['last_active']:
        sessions['last_active'].end_cc = float(matches.groups()[0])/1000
    return

def __close_sessions(sessions, state):
    if sessions['active']:
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
        __start_charge(sessions, state, matches)
        if not TECH and not VERBOSE:
            state['charging_start'] = __current_time(state)
    return

def discharging_regex_hook(sessions, state, matches):
    if sessions['charge'] is None:
        __missing_log_warning(sessions, state, 'charge')
    else:
        sessions['charge'] = None
    if sessions['discharge'] is not None:
        __missing_log_warning(sessions, state, 'discharge')
        sessions['discharge'] = None

    if not TECH and not VERBOSE:
        if state['charging_start'] == -2.0:
            state['charging_start'] = sessions['full'].start_time
        sessions['full'].usb_time += __current_time(state) - state['charging_start']
        state['charging_start'] = -1.0

    __start_discharge(sessions, state, matches)
    __start_wakeup(sessions, state, matches)
    if state['display'] == 'ON':
        __start_displayon(sessions, state, matches)
    else:
        __start_displayoff(sessions, state, matches)
    return

def deep_sleep_regex_hook(sessions, state, matches):
    __close_wakeup(sessions, state, matches)
    return

def cpu1_on(sessions, state, matches):
    if not TECH and not VERBOSE:
        state['cpu1_on'] = __current_time(state)
    return

def cpu1_off(sessions, state, matches):
    if not TECH and not VERBOSE:
        if state['cpu1_on'] == -2.0:
            state['cpu1_on'] = sessions['full'].start_time
        sessions['full'].cpu1_time += __current_time(state) - state['cpu1_on']
        state['cpu1_on'] = -1.0
    return

def __debug_print_all(sessions, state):
    print"sessions are:"
    for key in sessions.keys():
        if sessions[key]:
            print "---%s---"%key
            sessions[key].debug_print()
        else:
            print "---%s--- is None"%key
    print "state is:"
    for k in state.keys():
        print "%s is %s"%(k, state[k])

def roll(fobj_in, fobj_out):
    cur_state = __init_cur()
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
                    live_sessions['discharge'] = DischargeSession(
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
        # close all live sessions
        __close_sessions(live_sessions, cur_state)
        live_sessions['full'].end = cur_state['kernel_time_stamp']
        live_sessions['full'].end_time = __current_time(cur_state)
        live_sessions['full'].duration = __duration(live_sessions['full'])\
            + live_sessions['full'].rtc_only
    except:
        __debug_print_all(live_sessions, cur_state)
        raise
    if not TECH and not VERBOSE:
        if cur_state['cpu1_on'] > 0:
            live_sessions['full'].cpu1_time += __current_time(cur_state) - cur_state['cpu1_on']
        if cur_state['charging_start'] > 0:
            live_sessions['full'].usb_time += __current_time(cur_state) - cur_state['charging_start']
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

def print_summary(full):
    if not TECH and not VERBOSE:
        if full.duration == 0:
            print "Log file is invalid!"
            return
        else:
            if full.full_stats['DISPLAY']:
                total_cost = full.suspend_sum.cost + full.active_sum.cost +\
                    full.full_stats['DISPLAY'].values()[0].cost
                total_duration = full.suspend_sum.duration + full.active_sum.duration +\
                    full.full_stats['DISPLAY'].values()[0].duration
            else:
                total_cost = full.suspend_sum.cost + full.active_sum.cost
                total_duration = full.suspend_sum.duration + full.active_sum.duration
            if total_duration == 0:
                print 'Total log time:\t\t\t%s\t(100%%)'%(
                    full.duration
                    )
                print 'NO OTHER EVENTS FOUND IN THE LOG!'
                return
            else:
                print 'Total log time:\t\t\t%s\t(100%%) %0.2fmA'%(
                    total_duration,
                    total_cost*3600/total_duration
                    )
        if full.suspend_sum.duration == 0:
            print 'Total suspend time:\t\t0.00\t(0.00%)'
        else:
            print 'Total suspend time:\t\t%0.2f\t(%0.2f%%) %0.2fmA'%(
                full.suspend_sum.duration,
                full.suspend_sum.duration*100/full.duration,
                full.suspend_sum.cost*3600/full.suspend_sum.duration
                )
            print 'Total suspend count:\t\t%d'%(full.suspend_sum.count)
        print 'Total Active time:'
        if full.full_stats['DISPLAY']:
            print '\tTotal display on time:\t\t%0.2f\t(%0.2f%%) %0.2fmA'%(
                full.full_stats['DISPLAY'].values()[0].duration,
                full.full_stats['DISPLAY'].values()[0].duration*100/full.duration,
                full.full_stats['DISPLAY'].values()[0].cost*3600/
                full.full_stats['DISPLAY'].values()[0].duration)
        else:
            print '\tTotal display on time:\t\t0.00\t(0.00%)'
        if full.active_sum.duration == 0:
            print '\tTotal display off (active) time:0.00\t(0.00%)'
        else:
            print '\tTotal display off (active) time:%0.2f\t(%0.2f%%) %0.2fmA'%(
                full.active_sum.duration,
                full.active_sum.duration*100/full.duration,
                full.active_sum.cost*3600/full.active_sum.duration
                )
        print '\tTotal USB connected time:\t%0.2f\t(%0.2f%%)'%(
            full.usb_time,
            full.usb_time*100/full.duration
            )
        print '\tTotal CPU1 up time:\t\t%0.2f\t(%0.2f%%)'%(
            full.cpu1_time,
            full.cpu1_time*100/full.duration
            )
        print os.linesep
        print '\tWakeup Sources Ordered By Count'
        t = Top('count', len(full.full_stats['BACKGROUND'].values()))
        t.select(full.full_stats['BACKGROUND'].values())
        top_table(2, t.list, names={'name':INTERRUPTS})
        print '\tFreezing Abort Reasons Ordered By Count'
        t = Top('count', len(full.full_stats['ABORT'].values()))
        t.select(full.full_stats['ABORT'].values())
        top_table(2, t.list)
        print '\tDevice Failure Reasons Ordered By Count'
        t = Top('count', len(full.full_stats['DEVICE'].values()))
        t.select(full.full_stats['DEVICE'].values())
        top_table(2, t.list)
        print '\tLongest Wakelocks Ordered By Duration'
        t = Top('duration', len(full.full_stats['LONGEST'].values()))
        t.select(full.full_stats['LONGEST'].values())
        top_table(2, t.list, ['name','count','duration(seconds)'],\
            ['name','count','duration'])
        return
    else:
        print 'Overview'
        print '=============================='
        print os.linesep+'There are following discharge cycles logged:'
        top_table(2, full.discharge_sessions,\
                      ['Duration(seconds)','Start','End'],\
                      ['duration','start','end'],\
                      )
        print 'Following results are for the last discharge cycle:'
        print os.linesep+'Suspend/Wakeup Statistics'
        print '=============================='
        print 'Overall'
        last_discharge = full.discharge_sessions.pop()
        total_cost = 0.0
        awoken_sum = last_discharge.awoken_sum
        suspend_sum = last_discharge.suspend_sum
        total_duration = suspend_sum.duration + awoken_sum.duration
        total_cost = suspend_sum.cost + awoken_sum.cost
        cells = list()
        for i,j in [('Suspend', suspend_sum), ('Wake-Up', awoken_sum)]:
            if j.duration != 0:
                cells.append([i, '%.2f(%.1f%%)'%(j.duration, j.duration/total_duration*100),\
                                  '%.2f'%(j.cost),\
                                  '%.2f'%(j.cost*3600/j.duration)
                              ])
        table(1, ['', 'Total Duration(seconds)', 'Total Cost(mAh)', 'Average Current(mA)'], cells)
        # End of Overview

    print 'Reasons Keeping Phone active'
    cells = list()
    tops = dict()
    for n,d in [('From Suspend', awoken_sum.active_stats['BACKGROUND']),
                ('Freezing Abort', awoken_sum.active_stats['ABORT']),
                ('Device Failure', awoken_sum.active_stats['DEVICE']),
                ('Display On', awoken_sum.active_stats['DISPLAY']),
                ('Display Off', awoken_sum.active_stats['DISPLAYOFF']),
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

    print '\tTop Wakeup Sources in Count'
    t = Top('count')
    t.select(awoken_sum.active_stats['BACKGROUND'].values())
    top_table(2, t.list)
    print '\tTop Freezing Abort in Count'
    t = Top('count')
    t.select(awoken_sum.active_stats['ABORT'].values())
    top_table(2, t.list)
    print '\tTop Device Failure in Count'
    t = Top('duration')
    t.select(awoken_sum.active_stats['DEVICE'].values())
    top_table(2, t.list)
    print '\tLongest Display Session'
    top_table(2, full.tops['duration_displayon'].list,\
                  ['duration(seconds)','start','end','cost(mAh)'],\
                  ['duration','start','end','cost']\
                  )

    if VERBOSE == False:
        return

    print '=============================='
    print 'Hot Spots'
    print '=============================='
    print 'Top Wakeup Sources in Duration'
    t = Top('duration')
    t.select(awoken_sum.active_stats['BACKGROUND'].values())
    top_table(1, t.list)
    print 'Top Wakeup Sources in Cost'
    t = Top('cost')
    t.select(awoken_sum.active_stats['BACKGROUND'].values())
    top_table(1, t.list)
    print 'Top Freezing Abort in Duration'
    t = Top('duration')
    t.select(awoken_sum.active_stats['ABORT'].values())
    top_table(1, t.list)
    print 'Top Freezing Abort in Cost'
    t = Top('cost')
    t.select(awoken_sum.active_stats['ABORT'].values())
    top_table(1, t.list)
    print 'Top Device Failure in Duration'
    t = Top('count')
    t.select(awoken_sum.active_stats['DEVICE'].values())
    top_table(1, t.list)
    print 'Top Device Failure in Cost'
    t = Top('count')
    t.select(awoken_sum.active_stats['DEVICE'].values())
    top_table(1, t.list)
    print 'Top Blocking Wakelocks in Count'
    t = Top('count')
    t.select(awoken_sum.blocker_stats.values())
    top_table(1, t.list)
    print 'Top Blocking Wakelocks in Duration'
    t = Top('count')
    t.select(awoken_sum.blocker_stats.values())
    top_table(1, t.list)
    print 'Top Blocking Wakelocks in Cost'
    t = Top('count')
    t.select(awoken_sum.blocker_stats.values())
    top_table(1, t.list)

    print '=============================='
    print 'Hot Areas'
    print '=============================='

    print 'Longest Awoken Sessions'
    top_table(2, full.tops['duration_awoken'].list,\
                  ['duration(seconds)','start','end','cost(mAh)'],\
                  ['duration','start','end','cost',]\
                  )
    print 'Most Expensive Awoken Sessions'
    top_table(2, full.tops['cost_awoken'].list,\
                  ['cost','start','end','duration'],\
                  ['cost','start','end','duration'],\
                  )                  
    print 'Longest Display-off Active Sessions'
    top_table(2, full.tops['duration_active'].list,\
                  ['duration','start','end','cost'],\
                  ['duration','start','end','cost',]\
                  )
    print 'Most Expensive Display-off Active Sessions'
    top_table(2, full.tops['cost_active'].list,\
                  ['cost','start','end','duration'],\
                  ['cost','start','end','duration'],\
                  )
    print 'Longest Display-On Sessions'
    top_table(2, full.tops['duration_displayon'].list,\
                  ['duration','start','end','cost'],\
                  ['duration','start','end','cost',]\
                  )
    print 'Most Expensive Display-On Sessions'
    top_table(2, full.tops['cost_displayon'].list,\
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
    sys.stderr.write(SOFTWARE_NAME+' '+LAST_UPDATE+os.linesep)
    sys.stderr.write(AUTHOR+os.linesep)
    print "----"
    if len(sys.argv) < 2:
        __usage()

    parser = OptionParser()
    parser.add_option("-p", "--plat", dest="plat")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      default=VERBOSE,
                      help="")
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                      default=DEBUG,
                      help="")
    parser.add_option("-t", "--tech", action="store_true", dest="tech",
                      default=TECH,
                      help="")
    (options, args) = parser.parse_args(sys.argv)
    VERBOSE = options.verbose
    DEBUG = options.debug
    TECH = options.tech
    plat = options.plat
    objfile = args[1]

    __debug_print("DEBUG message is on!")
    platfile = os.path.dirname(os.path.realpath(__file__))+os.sep+plat+'.xml'
    if not os.path.isfile(platfile):
        __warning_print("%s is not fully supported yet"%plat)
    platxml = minidom.parseString(open(platfile).read())
    for i in BSP_REGEX.keys():
        append_regex(platxml, i, BSP_REGEX[i], REGEX)
    try:
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
#        fobj_out = open(objfile+'.csv', 'w')
    except Exception as e:
        __error_print('Opening input or output file'+
                      os.linesep + e)
        if fobj_in:
            fobj_in.close()
        sys.exit(1)

    f = roll(fobj_in, fobj_out)
    print_summary(f)

#    fobj_out.close()
    fobj_in.close()
# Main Sections Ends
################################################################################
