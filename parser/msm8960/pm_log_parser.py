import string,os,re,sys
from optparse import OptionParser


TOP = 5
SOFTWARE_NAME = 'log parser'
AUTHOR = 'Peng Liu - <a22543@motorola.com>'
LAST_UPDATE = 'Apr 06, 2012'

################################################################################
UNKNOWN = 'UNKNOWN'
TIME_UNIT = 1000000000
VERBOSE = False
# Utility functions
debug = True
def __debug_print(msg):
    if debug is True:
        sys.stderr.write('DEBUG: %s'%msg+os.linesep)
quiet = False
def __error_print(msg):
    if quiet is False:
        sys.stderr.write('ERROR: %s'%msg+os.linesep)

def __usage():
    sys.stderr.write('USAGE; python -u pm_log_parser.py <dmesg.txt>'+os.linesep)
    sys.stderr.write('Summary statistics will be printed to stdout '+
                     'and <dmesg.txt>.csv has details.'+os.linesep)
    sys.exit(1)

def __current_time(c):
    return float(c['kernel_time_stamp']) + KERNEL_TIME_LIMIT *\
        c['kernel_time_wrapup_counter']

#def __init_top(v):
#    t = list()
#    for i in range(TOP):
#        t.append(v)
#    return t
#
#def __place_value(k, v, t):
#    i = 0
#    while (i < TOP):
#        t1,t2 = t[i]
#        if v > t2:
#            break
#        i += 1
#    if i < TOP:
#        t.insert(i, (k,v))
#    return t[0:TOP]
#    
#
#def __find_top(d, t1, t2, t3):
#    for k in d.keys():
#        v1,v2,v3 = d[k]
#        __place_value(k,v1,t1)
#        __place_value(k,v2,t2)
#        __place_value(k,v3,t3)
################################################################################
# Not used yet
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

class Session(object):
    def __init__(self, start=UNKNOWN, end=UNKNOWN, duration=0.0, cost=0.0, typ=UNKNOWN, reason = UNKNOWN):
        self.start = start
        self.end = end
        self.cost = cost
        self.duration = duration
        self.type = typ
        self.reason = reason

class FullLogSession(Session):
    def __init__(self):
        super(FullLogSession, self).__init__()
        self.discharge_sessions = list()

suspend_result = {
    'UNKNOWN': -1,
    'SUCCESS': 0,
    'ABORTED': 1,
    'DEVICE': 2,
    'DISPLAY': 3,
    'BOOTUP': 999
    }

class AwokenSum(Sum):
    def __init__(self):
        super(AwokenSum, self).__init__()

        self.displayon_sum = Sum()
        self.displayoff_sum = Sum()

        self.resume_stats = dict()
        self.abort_stats = dict()
        self.failure_stats = dict()
        self.blocker_stats = dict()
        self.unknown_stats = dict()

        self.top_cost_displayon = Top('cost')
        self.top_duration_displayon = Top('duration')

        self.top_cost_active = Top('cost')
        self.top_duration_active = Top('duration')

        self.top_cost_awoken = Top('cost')
        self.top_duration_awoken = Top('duration')

class DischargeSession(Session):
    def __init__(self):
        super(DischargeSession, self).__init__()
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
    cur_state['last_active_reason'] = UNKNOWN
    cur_state['active_reason'] = UNKNOWN

    cur_state['kernel_time_stamp'] = ''
    cur_state['discharge_start_time'] = 0.0
    cur_state['discharge_start_ts'] = UNKNOWN
    cur_state['discharge_end_time'] = 0.0
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

    cur_state['discharging_start_time'] = -1.0
    cur_state['discharging_end_time'] = -1.0

    cur_state['gptimer_stop_time'] = 0.0

    return cur_state

################################################################################
# The Functions to be called when state changes
def __add_onto_elem_in_dict(d, k, number=0, duration=0, cost=0):
    if k not in d.keys():
        d[k] = Sum(k)
    d[k].update(number, duration, cost)

def __close_latest_displayon(c,s):
    time = c['sleep_time'] - c['wakeup_time']
    cost = c['sleep_coulomb'] - c['wakeup_coulomb']
    if cost < 0:
        cost = 0
        __error_print('cost < 0 at %s (%d - %d)'%\
                          (c['kernel_time_stamp'],
                           c['activated_coulomb'],
                           c['susp_kicked_coulomb']
                           )
                      )
        cost = float(cost)/1000
        session = Session(c['wakeup_ts'], c['sleep_ts'], time, cost)
        s.awoken_sum.displayon_sum.add(time, cost)
        s.awoken_sum.top_cost_displayon.insert(session)
        s.awoken_sum.top_duration_displayon.insert(session)
def __susp_kicked_enter_hook(c,s):
    if c['suspend_result'] == suspend_result['DISPLAY']:
        __close_latest_displayon(c,s)
    # counter value yet
    c['susp_kicked_time'] = __current_time(c)
    c['susp_kicked_ts'] = c['kernel_time_stamp']
    c['susp_kicked_coulomb'] = sys.maxint
    c['longest_wakelock_name'] = UNKNOWN
    c['longest_wakelock_len'] = 0.0
    c['failed_device'] = UNKNOWN
    c['active_wakelock'] = UNKNOWN
    c['last_active_reason'] = c['active_reason']
    c['active_reason'] = UNKNOWN
    return 

def __susp_kicked_leave_hook(c,s):
    # Last active session can be summarized here
    time = c['susp_kicked_time'] - c['activated_time']
    cost = c['susp_kicked_coulomb'] - c['activated_coulomb']
    if cost < 0:
        cost = 0
        __error_print('cost < 0 at %s (%d - %d)'%\
                          (c['kernel_time_stamp'],
                           c['susp_kicked_coulomb'],
                           c['activated_coulomb']
                           ))
    cost = float(cost)/1000
    session = Session(c['activated_ts'], c['susp_kicked_ts'], time, cost)
    if c['longest_wakelock_name'] != UNKNOWN:
        __add_onto_elem_in_dict(
            s.awoken_sum.blocker_stats,
            c['longest_wakelock_name'],
            1, c['longest_wakelock_len'], cost
            )
    s.awoken_sum.top_duration_active.insert(session)
    s.awoken_sum.top_cost_active.insert(session)

    r = UNKNOWN
    d = None
    a = None
    if c['suspend_result'] == suspend_result['SUCCESS']:
        d = s.awoken_sum.resume_stats
    elif c['suspend_result'] == suspend_result['DEVICE']:
        d = s.awoken_sum.failure_stats
    elif c['suspend_result'] == suspend_result['ABORTED']:
        d = s.awoken_sum.abort_stats
    elif c['suspend_result'] == suspend_result['DISPLAY']:
        s.awoken_sum.displayoff_sum.add(time, cost)
        return
    else:
        d = s.awoken_sum.unknown_stats
    
    __add_onto_elem_in_dict(
        d,
        c['last_active_reason'],
        1, time, cost
        )
    c['last_active_reason'] = UNKNOWN
    return

def __susp_aborted_enter_hook(c,s):
    c['suspend_result'] = suspend_result['ABORTED']
    c['activated_coulomb'] = c['susp_kicked_coulomb']
    c['susp_kicked_coulomb'] = sys.maxint
    return
def __susp_aborted_leave_hook(c,s):
    return

def __device_failed_enter_hook(c,s):
    c['suspend_result'] = suspend_result['DEVICE']
    c['activated_coulomb'] = c['susp_kicked_coulomb']
    c['susp_kicked_coulomb'] = sys.maxint
    return
def __device_failed_leave_hook(c,s):
    return

def __suspended_enter_hook(c,s):
    # last wakeup session can be summarized here
    c['suspend_result'] = suspend_result['SUCCESS']
    time = c['susp_kicked_time'] - c['resume_time']
    cost = c['susp_kicked_coulomb'] - c['resume_coulomb']
    if cost < 0:
        cost = 0
        __error_print('cost < 0 at %s (%d - %d)'%\
                          (c['kernel_time_stamp'],
                           c['susp_kicked_coulomb'],
                           c['resume_coulomb']
                           ))
    cost = float(cost)/1000
    s.awoken_sum.duration += time
    s.awoken_sum.cost += cost
    session = Session(c['resume_ts'], c['susp_kicked_ts'], time, cost)
    s.awoken_sum.top_cost_awoken.insert(session)
    s.awoken_sum.top_duration_awoken.insert(session)
    c['active_reason'] = UNKNOWN
    c['resume_coulomb'] = sys.maxint
    c['suspend_duration'] = 0.0
    return
def __suspended_leave_hook(c,s):
    c['gptimer_stop_time'] += c['suspend_duration']
    time = c['activated_time'] - c['susp_kicked_time'] + c['suspend_duration']
    cost = c['activated_coulomb'] - c['susp_kicked_coulomb']
    if cost < 0:
        cost = 0
        __error_print('cost < 0 at %s (%d - %d)'%\
                          (c['kernel_time_stamp'],
                           c['activated_coulomb'],
                           c['susp_kicked_coulomb']
                           )
                      )
    cost = float(cost)/1000
    s.suspend_sum.add(time, cost)
    c['resume_time'] = __current_time(c)
    c['resume_ts'] = c['kernel_time_stamp']
    c['resume_coulomb'] = c['activated_coulomb']
    return

def __resumed_enter_hook(c,s):
    # this time suspend duration
    c['activated_time'] = __current_time(c)
    c['activated_ts'] = c['kernel_time_stamp']
    c['sleep_coulomb'] = 0.0
    # TODO: should write into the spreadsheet file as well
    return

def __resumed_leave_hook(c,s):
    pass

def __charging_enter_hook(c,s):
    if c['suspend_result'] == suspend_result['DISPLAY']:
        __close_latest_displayon(c,s)
    s.end = c['kernel_time_stamp']
    c['discharging_end_time'] = __current_time(c)
    s.duration = __current_time(c) - c['discharging_start_time']
    # Finish awoken_sum
    # Finish activated session
    c['sleep_coulomb'] = 0.0
    c['discharge_start_time'] = -1.0
    c['discharge_start_ts'] = UNKNOWN
    c['discharge_end_time'] = 0.0
    return

def __charging_leave_hook(c,s):
    s.start = c['kernel_time_stamp']
    c['discharging_start_time'] = __current_time(c)
    return

def __displayon_enter_hook(c,s):
    if c['suspend_result'] == suspend_result['DISPLAY']:
        __close_latest_displayon(c,s)
    c['wakeup_ts'] = c['kernel_time_stamp']
    c['wakeup_time'] = __current_time(c)
    c['display'] = 'ON'
    c['wakeup_coulomb'] = sys.maxint
    return

def __displayon_leave_hook(c,s):
    # Can close the active session before display turned on
    time = __current_time(c) - c['wakeup_time']
    cost = c['wakeup_coulomb'] - c['activated_coulomb']
    if cost < 0:
        cost = 0
        __error_print('cost < 0 at %s (%d - %d)'%\
                          (c['kernel_time_stamp'],
                           c['susp_kicked_coulomb'],
                           c['activated_coulomb']
                           ))
    cost = float(cost)/1000
    session = Session(c['activated_ts'], c['wakeup_ts'], time, cost)
    s.awoken_sum.top_duration_active.insert(session)
    s.awoken_sum.top_cost_active.insert(session)
    r = UNKNOWN
    d = None
    a = None
    if c['suspend_result'] == suspend_result['SUCCESS']:
        d = s.awoken_sum.resume_stats
    elif c['suspend_result'] == suspend_result['DEVICE']:
        d = s.awoken_sum.failure_stats
    elif c['suspend_result'] == suspend_result['ABORTED']:
        d = s.awoken_sum.abort_stats
    elif c['suspend_result'] == suspend_result['DISPLAY']:
        s.awoken_sum.displayoff_sum.add(time, cost)
        return
    else:
        d = s.awoken_sum.unknown_stats
    
    __add_onto_elem_in_dict(
        d,
        c['last_active_reason'],
        1, time, cost
        )
    c['last_active_reason'] = UNKNOWN
    c['active_reason'] = 'DISPLAY'

    c['sleep_time'] = __current_time(c)
    c['sleep_ts'] = c['kernel_time_stamp']
    c['active_time'] = __current_time(c)
    c['active_ts'] = c['kernel_time_stamp']
    c['suspend_result'] = suspend_result['DISPLAY']
    c['display'] = 'OFF'
    return

# The Functions to be called when state changes
################################################################################

################################################################################
# Regular Expressions and Their Handlers
NEXT_STATE = {
    'preparing': 'SUSP_KICKED',
    'aborted1': 'SUSP_ABORTED',
    'aborted2': 'SUSP_ABORTED',
    'aborted3': 'SUSP_ABORTED',
    'devicefailed': 'DEVICE_FAILED',
    'suspended': 'SUSPENDED',
    'booting': 'RESUMED',
    'resumed': 'RESUMED',
    'sleep': 'RESUMED',
    'wakeup': 'DISPLAYON',
    'charging': 'CHARGING',
    }
ACTIVITIES = {
    'preparing': re.compile('PM: Preparing system for mem sleep'),
    'aborted1': re.compile('Freezing of tasks  aborted'),
    'aborted2': re.compile('Freezing of user space  aborted'),
    'aborted3': re.compile('suspend aborted....'),
    'devicefailed': re.compile('PM: Some devices failed to [(suspend)|(power down)]'),
    'suspended': re.compile('msm_pm_enter: power collapse'),
    'booting': re.compile('Booting Linux'),
    'resumed': re.compile('suspend: exit suspend, ret = [^ ]+ \((\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{9}) UTC\)'),
    'sleep': re.compile('request_suspend_state: sleep (0->3)'),
    'wakeup': re.compile('request_suspend_state: wakeup (3->0)'),
    'charging': re.compile('msm_otg msm_otg: Avail curr from USB = ([1-9]\d*)'),
    'discharging': re.compile('msm_otg msm_otg: Avail curr from USB = 0$'),
    }
def common_activity_hook(c,m,s,k):
    next = NEXT_STATE[k]
    if c['state'] == next:
        return None
    __state_leave_hook(c,s)
    c['state'] = next
    __state_enter_hook(c,s)
    return c['state']

def booting_activity_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['booting']
    and the summary structure
    and the first part of this function name
    """
    __state_leave_hook(c,s)
    c['active_reason'] = 'bootup'
    c['suspend_result'] = suspend_result['BOOTUP']
    c['resume_coulomb'] = 0
    c['resume_time'] = 0.0
    c['resume_ts'] = '0.0'
    c['activated_coulomb'] = 0
    c['activated_time'] = 0
    c['state'] = k
    c['display'] = 'OFF'
    c['charging'] = 'OFF'
    c['discharge_start_time'] = 0.0
    c['discharge_start_ts'] = '0.0'
    c['state'] = NEXT_STATE[k]
    __state_enter_hook(c,s)
    return c['state']

def sleep_activity_hook(c,m,s,k):
    c['display'] = 'OFF'
    if c['state'] == 'RESUMED' or c['state'] == 'CHARGING':
        return c['state']
    __state_leave_hook(c,s)
    c['state'] = 'RESUMED'
    __state_enter_hook(c,s)
    return c['state']

def wakeup_activity_hook(c,m,s,k):
    c['display'] = 'ON'
    if c['state'] == 'DISPLAYON' or c['state'] == 'CHARGING':
        return c['state']
    __state_leave_hook(c,s)
    c['state'] = 'DISPLAYON'
    __state_enter_hook(c,s)
    return c['state']

def charging_activity_hook(c,m,s,k):
    if c['state'] == 'CHARGING':
        return c['state']
    __state_leave_hook(c,s)
    c['state'] = 'CHARGING'
    __state_enter_hook(c,s)
    return c['state']

def discharging_activity_hook(c,m,s,k):
    if c['state'] != 'CHARGING':
        return c['state']
    if c['display'] == 'ON':
        next = 'DISPLAYON'
    else:
        next = 'RESUMED'
    __state_leave_hook(c,s)
    c['state'] = next
    __state_enter_hook(c,s)
    return next

DATA = {
    'susp_kicked_coulomb': (re.compile('pm_debug: suspend uah=(-{0,1}\d+)')),
    'resume_coulomb': (re.compile('pm_debug: resume uah=(-{0,1}\d+)')),
    'active_wakelock': (re.compile('active wake lock ([^, ]+),*')),
    'longest_wakelock': (re.compile('longest wake lock: \[([^\]]+)\]\[(\d+)\]')),
    'wakeup_wakelock': (re.compile('wakeup wake lock: (\w+)')),
    'suspend_duration': (re.compile('suspend: e_uah=-{0,1}\d+ time=(\d+)')),
    'failed_device': (re.compile('PM: Device ([^ ]+) failed to suspend')),
    'sleep_coulomb': (re.compile('pm_debug: sleep uah=(-{0,1}\d+)')),
    'wakeup_coulomb': (re.compile('pm__debug: wakeup uah=(-{0,1}\d+)')),
    }
def susp_kicked_coulomb_data_hook(c,m):
    w = m.groups()[0]
    c['susp_kicked_coulomb'] = int(w)
    return

def resume_coulomb_data_hook(c,m):
    w = m.groups()[0]
    c['activated_coulomb'] = int(w)
    c['resume_coulomb'] = int(w)
    return

def active_wakelock_data_hook(c,m):
    """
    inputs are current system state
    and matched module gotten from REs['active_wakelock']
    and the summary structure
    and the first part of this function name
    """
    c['active_reason'] = m.groups()[0]
    return

def longest_wakelock_data_hook(c,m):
    """
    inputs are current system state
    and matched module gotten from REs['longest_wakelock']
    and the summary structure
    and the first part of this function name
    """
    c['longest_wakelock_name'] = m.groups()[0]
    c['longest_wakelock_len'] = float(m.groups()[1])
    return

def wakeup_wakelock_data_hook(c,m):
    """
    inputs are current system state
    and matched module gotten from REs['wakeup_wakelock']
    and the summary structure
    and the first part of this function name
    """
    w = m.groups()[0]
    c['active_reason'] = w
    return

def suspend_duration_data_hook(c,m):
    """
    inputs are current system state
    and matched module gotten from REs['suspend_duration']
    and the summary structure
    and the first part of this function name
    """
    w = m.groups()[0]
    c['suspend_duration'] = float(w)/TIME_UNIT
    return

def failed_device_data_hook(c,m):
    """
    inputs are current system state
    and matched module gotten from REs['failed_device']
    and the summary structure
    and the first part of this function name
    """
    d = m.groups()[0]
    c['active_reason'] = d
    return

def sleep_coulomb_data_hook(c,m):
    w = m.groups()[0]
    c['sleep_coulomb'] = int(w)
    c['activated_coulomb'] = int(w)
    c['display'] = 'OFF'
    return

def wakeup_coulomb_data_hook(c,m):
    w = m.groups()[0]
    c['wakeup_coulomb'] = int(w)
    c['display'] = 'ON'
    return

# Regular Expressions and Their Handlers End
################################################################################

################################################################################
def __state_enter_hook(c,s):
    x_name = string.lower("__%s_enter_hook"%c['state'])
    if x_name in globals().keys():
        x = globals()[x_name]
        x(c,s)

def __state_leave_hook(c,s):
    x_name = string.lower("__%s_leave_hook"%c['state'])
    if x_name in globals().keys():
        x = globals()[x_name]
        x(c,s)

# State Machine Section Starts
NEXT_ACTIVITY = {
    'SUSP_KICKED':
        ['devicefailed',
         'suspended',
         'aborted1',
         'aborted2',
         'aborted3',
         ],
    'DEVICE_FAILED':
        ['resumed',
         ],
    'SUSPENDED':
        ['wakeup',
         'resumed',
         ],
    'SUSP_ABORTED':
        ['resumed'
         ],
    'RESUMED':
        ['preparing',
         'charging',
         'wakeup',
         'resumed',
         'discharging',
         ],
    'UNKNOWN':
        ['booting',
         'resumed',
         'preparing',
         'devicefailed',
         'suspended',
         'aborted1',
         'aborted2',
         'aborted3',
         'sleep',
         'wakeup',
         'charging',
         'discharging',
         ],
    'CHARGING':
        ['discharging',
         ],
    'DISPLAYON':
        ['charging',
         'sleep'
         ],
    }
COLLECTING_DATA = {
    'SUSP_KICKED':
        ['susp_kicked_coulomb',
         'longest_wakelock',
         'failed_device',
         'active_wakelock',
         ],
    'SUSP_ABORTED':
        ['active_wakelock',
         'resume_coulomb',
         ],
    'DEVICE_FAILED':
        ['resume_coulomb',
         ],
    'SUSPENDED':
        ['wakeup_wakelock',
         'resume_coulomb',
         'suspend_duration',
         ],
    'RESUMED':
        ['sleep_coulomb',
        ],
    'CHARGING':
        [
         ],
    'DISPLAYON':
        ['wakeup_coulomb',
         ],
    'UNKNOWN':
        ['susp_kicked_coulomb',
         'resume_coulomb',
         'active_wakelock',
         'longest_wakelock',
         'wakeup_wakelock',
         'suspend_duration',
         'failed_device',
         'sleep_coulomb',
         'wakeup_coulomb',
         ],
    }

def __match_activity(log):
    """
    Return a pair. The first value is matched regex. 
    The third one is matched result.
    """
    key = None
    matched = None
    for k in ACTIVITIES.keys():
        r = ACTIVITIES[k]
        m = r.match(log)
        if m is not None:
            matched = m
            key = k
            break
    return key,matched

def __collect_data(c, log):
    data = None
    matched = None
    state = c['state']
    for k in COLLECTING_DATA[state]:
        r = DATA[k]
        m = r.match(log)
        if m is not None:
            data = k
            matched = m
            break;
    return data,matched

# State Machine Section Ends
################################################################################
################################################################################
# Log Processing Section Starts
KERNEL_TIME_LIMIT = 131072.0
KERNEL_TIME_STAMP =\
    re.compile('^<\d>\[ *(\d+)\.(\d{6}).*\] (.*)')
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
    'booting': re.compile('Booting Linux'),
    'preparing': re.compile('PM: Preparing system for mem sleep'),
    'aborted1': re.compile('Freezing of tasks  aborted'),
    'aborted2': re.compile('Freezing of user space  aborted'),
    'aborted3': re.compile('suspend aborted....'),
    'devicefailed': re.compile('PM: Some devices failed to [(suspend)|(power down)]'),
    'resumed': re.compile('suspend: exit suspend, ret = [^ ]+ \((\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{9}) UTC\)'),
    'failed_device': (re.compile('PM: Device ([^ ]+) failed to suspend')),
    # Motorola debug info
    'susp_kicked_coulomb': (re.compile('pm_debug: suspend uah=(-{0,1}\d+)')),
    'resume_coulomb': (re.compile('pm_debug: resume uah=(-{0,1}\d+)')),
    'longest_wakelock': (re.compile('longest wake lock: \[([^\]]+)\]\[(\d+)\]')),
    'suspend_duration': (re.compile('suspend: e_uah=-{0,1}\d+ time=(\d+)')),
    'sleep_coulomb': (re.compile('pm_debug: sleep uah=(-{0,1}\d+)')),
    'wakeup_coulomb': (re.compile('pm_debug: wakeup uah=(-{0,1}\d+)')),
    'active_wakelock': (re.compile('active wake lock ([^, ]+),*')),
    'sleep': re.compile('request_suspend_state: sleep (0->3)'),
    'wakeup': re.compile('request_suspend_state: wakeup (3->0)'),
    'wakeup_wakelock': (re.compile('wakeup wake lock: (\w+)')),
    # MSM
    'suspended': re.compile('msm_pm_enter: power collapse'),
    'charging': re.compile('msm_otg msm_otg: Avail curr from USB = ([1-9]\d*)'),
    'discharging': re.compile('msm_otg msm_otg: Avail curr from USB = 0$'),
    }

def roll(fobj_in, fobj_out):
    cur_state = __init_cur()
    live_sessions = dict()
    live_sessions['full'] = None
    live_sessions['discharge'] = None
    live_sessions['charge'] = None
    live_sessions['active'] = None
    live_sessions['suspend'] = None

    l = fobj_in.readline()
    while (len(l)):
        t,b = time_and_body(l)
        if t is not None:
            if not live_sessions['full']:
                live_sessions['full'] = Session(start=t)
            for k in REGEX.keys():
                r = REGEX[k]
                m = r.match(l)
                if m is not None:
                    if '%s_regex_hook'%k in globals().keys():
                        hook = globals()['%s_regex_hook'%k]
                        hook(live_sessions, cur_state, m)
    # close all live sessions
    for e in live_sessions.values():
        if e:
            e.finish(cur_state)
    return live_sessions['full'], live_sessions['discharge']

def run(fobj_in, fobj_out):
    """ """
    # All stats dict values have following format:
    # (count, duration, cost)
    # The initilization order below is exactly how they are shown in print_sum()
    full = FullLogSession()
    disch = None
    cur_state = __init_cur()

    l = fobj_in.readline()
    while (len(l)):
        t,b = time_and_body(l)
        if t is not None:
            # Check if there's kernel time wrap-up
            if disch is None:
                disch = DischargeSession()
                discharging_activity_hook(cur_state, None, disch, None)
            else:
                if float(t) < __current_time(cur_state):
                    cur_state['kernel_time_wrapup_counter'] += 1
            cur_state['kernel_time_stamp'] = t
            # Use hook function to make statistics and spreadsheet
            k,m = __match_activity(b)
            if k is not None:
                c = cur_state['state']
                if k not in NEXT_ACTIVITY[c]:
                    __error_print('There might be log missing before%s%s'%
                                  (os.linesep, l))
                if '%s_activity_hook'%k in globals().keys():
                    hook = globals()['%s_activity_hook'%k]
                else:
                    hook = common_activity_hook
                next_state = hook(cur_state, m, disch, k)
                if next_state == 'CHARGING' and c != 'CHARGING':
                    full.discharge_sessions.append(disch)
                    disch = DischargeSession()
            else:
                k,m =__collect_data(cur_state, b)
                if k:
                    hook = globals()['%s_data_hook'%k]
                    hook(cur_state, m)
        l = fobj_in.readline()
    # This is ugly but necessary: pretending there is a final resumed state, if
    # we're going to enter suspend at the end of the log
    charging_activity_hook(cur_state, None, disch, None)
    full.discharge_sessions.append(disch)
    return full,disch

TAB_WIDTH = 8
TAB_2_WIDTH = 32

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

def top_table(tab_n, top_list,\
                  header=['name','count','duration(seconds)','cost(mAh)'],\
                  fields=['name','count','duration','cost'],\
                  width = [TAB_2_WIDTH]*4):
    cells = list()
    for i in top_list:
        line = list()
        for f in fields:
            line.append('%s'%getattr(i, f))
        cells.append(line)
    table(tab_n, header, cells, width)
    return

def print_summary(full,last_discharge):
    print '=============================='
    print 'Logging Facts'
    print '=============================='
    print 'There are following discharge periods:'
    top_table(2, full.discharge_sessions,\
                  ['Duration(seconds)','Start','End'],\
                  ['duration','start','end'],\
                  )
    print '=============================='
    print 'Suspend/Wakeup Statistics'
    print '=============================='
    print 'Overall'
    last_discharge = full.discharge_sessions.pop()
    total_cost = 0.0
    awoken_sum = last_discharge.awoken_sum
    suspend_sum = last_discharge.suspend_sum
    total_duration = suspend_sum.duration + awoken_sum.duration
    total_cost = suspend_sum.cost + awoken_sum.cost
    if total_cost == 0.0:
        print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        print 'Can\'t Work On User Build Log. OR last discharge session is too short!'
        print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        return
    cells = list()
    for i,j in [('Suspend', suspend_sum), ('Wake-Up', awoken_sum)]:
        if j.duration != 0:
            cells.append([i, '%.2f(%.2f)'%(j.duration, j.duration/total_duration),\
                              '%.2f(%.2f)'%(j.cost, j.cost/total_cost),\
                              '%.2f'%(3600*j.cost/j.duration)
                          ])
    table(1, ['', 'Total Duration(seconds)', 'Total Cost(mAh)', 'Average Current(mA)'], cells)
    print 'Wake-Ups'
    cells = list()
    tops = dict()
    for n,d in [('From Suspend', awoken_sum.resume_stats),
                ('Freezing Abort', awoken_sum.abort_stats),
                ('Device Failure', awoken_sum.failure_stats),
                ('Unknown Reason', awoken_sum.unknown_stats),
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
    t.select(awoken_sum.resume_stats.values())
    top_table(2, t.list)
    print '\tTop Freezing Abort in Count'
    t = Top('count')
    t.select(awoken_sum.abort_stats.values())
    top_table(2, t.list)
    print '\tTop Device Failure in Count'
    t = Top('duration')
    t.select(awoken_sum.failure_stats.values())
    top_table(2, t.list)

    if VERBOSE == False:
        return

    print '=============================='
    print 'Hot Spots'
    print '=============================='
    print 'Top Wakeup Sources in Duration'
    t = Top('duration')
    t.select(awoken_sum.resume_stats.values())
    top_table(1, t.list)
    print 'Top Wakeup Sources in Cost'
    t = Top('cost')
    t.select(awoken_sum.resume_stats.values())
    top_table(1, t.list)
    print 'Top Freezing Abort in Duration'
    t = Top('duration')
    t.select(awoken_sum.abort_stats.values())
    top_table(1, t.list)
    print 'Top Freezing Abort in Cost'
    t = Top('cost')
    t.select(awoken_sum.abort_stats.values())
    top_table(1, t.list)
    print 'Top Device Failure in Duration'
    t = Top('count')
    t.select(awoken_sum.failure_stats.values())
    top_table(1, t.list)
    print 'Top Device Failure in Cost'
    t = Top('count')
    t.select(awoken_sum.failure_stats.values())
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
    top_table(1, awoken_sum.top_duration_awoken.list,\
                  ['duration(seconds)','start','end','cost(mAh)'],\
                  ['duration','start','end','cost',]\
                  )
    print 'Most Expesive Awoken Sessions'
    top_table(1, awoken_sum.top_cost_awoken.list,\
                  ['cost','start','end','duration'],\
                  ['cost','start','end','duration'],\
                  )                  
    print 'Longest Display-off Active Sessions'
    top_table(1, awoken_sum.top_duration_active.list,\
                  ['duration','start','end','cost'],\
                  ['duration','start','end','cost',]\
                  )
    print 'Most Expensive Display-off Active Sessions'
    top_table(1, awoken_sum.top_cost_active.list,\
                  ['cost','start','end','duration'],\
                  ['cost','start','end','duration'],\
                  )
    print 'Longest Display-On Sessions'
    top_table(1, awoken_sum.top_duration_displayon.list,\
                  ['duration','start','end','cost'],\
                  ['duration','start','end','cost',]\
                  )
    print 'Most Expensive Display-On Sessions'
    top_table(1, awoken_sum.top_cost_displayon.list,\
                  ['duration','start','end','cost'],\
                  ['duration','start','end','cost',]\
                  )
    return

if __name__ == "__main__":
    sys.stderr.write(SOFTWARE_NAME+' '+LAST_UPDATE+os.linesep)
    sys.stderr.write(AUTHOR+os.linesep)

    if len(sys.argv) < 2:
        __usage()

    parser = OptionParser()
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      default=False,
                      help="")
    (options, args) = parser.parse_args(sys.argv)
    VERBOSE = options.verbose
    objfile = args[1]

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

    f,s = run(fobj_in, fobj_out)
    print_summary(f,s)

#    fobj_out.close()
    fobj_in.close()
# Main Sections Ends
################################################################################
