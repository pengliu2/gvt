import string,os,re,sys

TOP = 5
SOFTWARE_NAME = 'log parser'
AUTHOR = 'Peng Liu - <a22543@motorola.com>'
LAST_UPDATE = 'Apr 06, 2012'

################################################################################
UNKNOWN = 'UNKNOWN'
TIME_UNIT = 1000000000

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
    return c['kernel_log_end_ts'] + KERNEL_TIME_LIMIT *\
        c['kernel_time_wrapup_counter']

def __init_top(v):
    t = list()
    for i in range(TOP):
        t.append(v)
    return t

def __place_value(k, v, t):
    i = 0
    while (i < TOP):
        t1,t2 = t[i]
        if v > t2:
            break
        i += 1
    if i < TOP:
        t.insert(i, (k,v))
    return t[0:TOP]
    

def __find_top(d, t1, t2, t3):
    for k in d.keys():
        v1,v2,v3 = d[k]
        __place_value(k,v1,t1)
        __place_value(k,v2,t2)
        __place_value(k,v3,t3)

class Stats(object):
    def __init__(self, name):
        self.name = name
        self.count = 0
        self.duration = 0.0
        self.cost = 0.0

class Session(object):
    def __init__(self, name):
        self.name = name
        self.start = -1.0
        self.end = 0
        self.duration = 0.0
        self.cost = 0.0
        self.children = dict()
        self.states = dict()

class FullLogSession(Session):
    def __init__(self, name):
        super(FullLogSession, self).__init__(name)
        self.discharge_sessions = list()
        self.discharge_stats = Stats()

class DischargeSession(Session):
    def __init__(self, name):
        super(FullLogSession, self).__init__(name)

class WakeupSession(Session):
    pass

class SuspendSession(Session):
    pass

class DisplayOnSession(Session):
    pass

class DisplayOffSession(Session):
    pass

class ActiveSession(Session):
    pass

def __init_sum():
    summary = dict()
    summary['kernel_log_duration'] = 0
    summary['session_stats'] = dict() # active,suspend
#    summary['active_stats'] = (0,0,0)
    summary['suspend_attempt_counter'] = 0
    summary['device_failed_counter'] = 0
    summary['freezing_abort_counter'] = 0
#    summary['successful_suspend_stats'] = (0,0,0)
    summary['rtc_stop_time'] = 0

    summary['active_wakelock_stats'] = dict()
    summary['device_failed_stats'] = dict()
    summary['wakeup_wakelock_stats'] = dict()
    summary['wakeup_source_stats'] = dict()
    summary['longest_wakelock_stats'] = dict()
    summary['irq_stats'] = dict()

    summary['top_costly_wakeup_session'] = __init_top(('',-1.0))
    summary['top_longest_wakeup_session'] = __init_top(('',-1.0))
    summary['top_costly_blocking_session'] = __init_top(('',-1.0))
    summary['top_longest_blocking_session'] = __init_top(('',-1.0))
    summary['top_costly_blocking_wakelock'] = __init_top(('',-1.0))
    summary['top_longest_blocking_wakelock'] = __init_top(('',-1.0))
    summary['top_costly_active_session'] = __init_top(('',-1.0))
    summary['top_longest_active_session'] = __init_top(('',-1.0))
    summary['top_costly_suspend_session'] = __init_top(('',-1.0))
    summary['top_longest_suspend_session'] = __init_top(('',-1.0))
    return summary
def __init_cur():
    cur_state = dict()
    cur_state['state'] = UNKNOWN

    # This is for the last resume from successful suspend
    cur_state['resume_time'] = -1.0
    cur_state['resume_coulomb'] = sys.maxint
    # This is for the last suspend attempt, no matter if successful or not
    cur_state['susp_kicked_time'] = -1.0
    # This is for the nearest suspend attempt
    cur_state['suspend_result'] = suspend_result['SUCCESS']
    cur_state['susp_kicked_coulomb'] = sys.maxint
    cur_state['suspend_duration'] = 0
    # This is for the nearest activating
    cur_state['activated_coulomb'] = sys.maxint
    cur_state['activated_time'] = -1.0
    # This is for tne nearest resume
    cur_state['wakeup_source'] = UNKNOWN
    cur_state['wakeup_wakelock'] = UNKNOWN
    cur_state['last_wakeup_wakelock'] = UNKNOWN

    cur_state['failed_device'] = UNKNOWN
    cur_state['active_wakelock'] = UNKNOWN
    cur_state['last_failed_device'] = UNKNOWN
    cur_state['last_active_wakelock'] = UNKNOWN

    cur_state['kernel_time_stamp'] = ''
    cur_state['kernel_log_start_ts'] = -1.0
    cur_state['kernel_log_end_ts'] = 0.0
    cur_state['kernel_time_wrapup_counter'] = 0

    cur_state['longest_wakelock_name'] = None
    cur_state['longest_wakelock_len'] = 0

    cur_state['charger'] = general_state['UNKNOWN']
    cur_state['display'] = general_state['UNKNOWN']
    return cur_state

################################################################################
# The Functions to be called when state changes
def __add_onto_elem_in_dict(d, k, v):
    if k in d.keys():
        v0,v1,v2 = d[k]
        d[k] = (v[0]+v0, v[1]+v1, v[2]+v2)
    else:
        d[k] = v

def __susp_kicked_enter(c,s):
    c['state'] = 'SUSP_KICKED'
    return 
def __susp_kicked_leave(c,s):
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
    d = dict()
    r = UNKNOWN
    if c['suspend_result'] == suspend_result['SUCCESS']:
        d = s['wakeup_wakelock_stats']
        r = c['last_wakeup_wakelock']
    elif c['suspend_result'] == suspend_result['DEVICE']:
        d = s['device_failed_stats']
        r = c['last_failed_device']
    elif c['suspend_result'] == suspend_result['ABORTED']:
        d = s['active_wakelock_stats']
        r = c['last_active_wakelock']
    __add_onto_elem_in_dict(
        d,
        r,
        (1, time, cost)
        )
    if c['longest_wakelock_name']:
        __add_onto_elem_in_dict(
            s['longest_wakelock_stats'],
            c['longest_wakelock_name'],
            (1, c['longest_wakelock_len'], 0)
            )
        # checks if this longest_wakelock is on top
        s['top_longest_blocking_wakelock'] = __place_value(
            c['kernel_time_stamp'],
            c['longest_wakelock_len'],
            s['top_longest_blocking_wakelock']
            )
    __add_onto_elem_in_dict(
        s['session_stats'],
        'active',
        (1, time, cost)
        )
    s['top_longest_active_session'] = __place_value(
        c['kernel_time_stamp'],
        time,
        s['top_longest_active_session'])
    s['top_costly_active_session'] = __place_value(
        '%s %f'%(c['kernel_time_stamp'],cost/time),
        cost,
        s['top_costly_active_session']
        )
    c['longest_wakelock_name'] = None
    return

def __susp_aborted_enter(c,s):
    s['freezing_abort_counter'] += 1
    c['suspend_result'] = suspend_result['ABORTED']
    c['state'] = 'SUSP_ABORTED'
    c['activated_coulomb'] = c['susp_kicked_coulomb']
    c['susp_kicked_coulomb'] = sys.maxint
    return
def __susp_aborted_leave(c,s):
    s['suspend_attempt_counter'] += 1
    c['last_active_wakelock'] = c['active_wakelock']
    return

def __device_failed_enter(c,s):
    s['device_failed_counter'] += 1
    c['state'] = 'DEVICE_FAILED'
    c['suspend_result'] = suspend_result['DEVICE']
    c['activated_coulomb'] = c['susp_kicked_coulomb']
    c['susp_kicked_coulomb'] = sys.maxint
    return
def __device_failed_leave(c,s):
    s['suspend_attempt_counter'] += 1
    c['last_failed_device'] = c['failed_device']
    return

def __suspended_enter(c,s):
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
    s['top_costly_wakeup_session'] = __place_value(
        '%s %f'%(c['kernel_time_stamp'],cost/time),
        cost,
        s['top_costly_wakeup_session']
        )

    # See if last wakeup session is on top
    s['top_longest_wakeup_session'] = __place_value(
        c['kernel_time_stamp'],
        time,
        s['top_longest_wakeup_session']
        )
    c['state'] = 'SUSPENDED'
    c['last_wakeup_wakelock'] = c['wakeup_wakelock']
    return
def __suspended_leave(c,s):
    s['suspend_attempt_counter'] += 1
    s['rtc_stop_time'] += c['suspend_duration']
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
    __add_onto_elem_in_dict(
        s['session_stats'],
        'suspend',
        (1, time, cost)
        )
    s['top_costly_suspend_session'] = __place_value(
        '%s %f'%(c['kernel_time_stamp'],cost/time),
        cost,
        s['top_costly_suspend_session']
        )
    s['top_longest_suspend_session'] = __place_value(
        c['kernel_time_stamp'],
        time,
        s['top_longest_suspend_session']
        )
    c['resume_time'] = __current_time(c)
    c['resume_coulomb'] = c['activated_coulomb']
    return

def __resumed_leave(c,s):
    pass
def __resumed_enter(c,s):
    # this time suspend duration
    c['state'] = 'RESUMED'
    # TODO: should write into the spreadsheet file as well
    return
# The Functions to be called when state changes
################################################################################

################################################################################
# Regular Expressions and Their Handlers
# These are the meanings of prefixes
# f stands for freezing
# a stands for abort of freezing
# s stands for sleeping
# w stands for waking-up
ACTIVITIES = {
    'preparing': (re.compile('PM: Preparing system for mem sleep'),
           'SUSP_KICKED'
           ),
    'aborted1': (re.compile('Freezing of tasks  aborted'),
           'SUSP_ABORTED'
           ),
    'aborted2': (re.compile('Freezing of user space  aborted'),
           'SUSP_ABORTED'
           ),
    'aborted3': (re.compile('suspend aborted....'),
           'SUSP_ABORTED'
           ),                 
    'devicefailed': (re.compile('PM: Some devices failed to [(suspend)|(power down)]'),
                      'DEVICE_FAILED'
                      ),
    'suspended': (re.compile('msm_pm_enter: power collapse'),
           'SUSPENDED'
           ),
    'booting': (re.compile('Booting Linux'),
           'RESUMED'
           ),
    'resumed': (re.compile('suspend: exit suspend, ret = [^ ]+ \((\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{9}) UTC\)'),
           'RESUMED'
           ),
#    'sleep': (re.compile('request_suspend_state: sleep (0->3)'),
#              'DISPLAY-OFF'
#              ),
#    'wakeup': (re.compile('request_suspend_state: wakeup (3->0)'),
#               'DISPLAY-ON'
#               ),
#    'charging': (re.compile('msm_otg msm_otg: Avail curr from USB = ([1-9]\d*)'),
#                'CHARGING'
#                 ),
#    'discharging': (re.compile('msm_otg msm_otg: Avail curr from USB = 0$'),
#                    'DISCHARGING'
#                    ),
    }
DATA = {
    'suspend_current': (re.compile('pm_debug: suspend uah=(-{0,1}\d+)')),
    'resume_current': (re.compile('pm_debug: resume uah=(-{0,1}\d+)')),
    'active_wakelock': (re.compile('active wake lock ([^,]+),*')),
    'longest': (re.compile('longest wake lock: \[([^\]]+)\]\[(\d+)\]')),
    's2': (re.compile('RESERVED FOR POWER STATE')),
    'w1': (re.compile('RESERVED FOR WAKEUP IRQ')),
    'wakeup_wakelock': (re.compile('wakeup wake lock: (\w+)')),
    'suspend_duration': (re.compile('suspend: e_uah=-{0,1}\d+ time=(\d+)')),
    'failed_device': (re.compile('PM: Device ([^ ]+) failed to suspend')),
    }
def __state_change_hook(c,s,k):
    x_name = string.lower("__%s_leave"%c['state'])
    if x_name in globals().keys():
        x = globals()[x_name]
        x(c,s)
    r,state = ACTIVITIES[k]
    x_name = string.lower("__%s_enter"%state)
    if x_name in globals().keys():
        x = globals()[x_name]
        x(c,s)

def __log_end(c, s):
    state = c['state']
    if state == 'SUSP_KICKED'\
            or state == 'SUSP_ABORTED'\
            or state == 'DEVICE_FAILED'\
            or state == 'SUSPENDED'\
            or state == 'RES_KICKED':
        __resumed_enter(c, s)
    elif state == 'RESUMED':
        ta = __current_time(c) - c['activated_time']
        __add_onto_elem_in_dict(
            s['session_stats'],
            'active',
            (1, ta, 0))
        __add_onto_elem_in_dict(
            s['wakeup_wakelock_stats'],
            c['wakeup_wakelock'],
            (1,
             ta,
             0
             )
            )

def preparing_activity_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['f1']
    and the summary structure
    and the first part of this function name
    """
    c['susp_kicked_time'] = __current_time(c)
    __state_change_hook(c,s,k)
    return 

def aborted1_activity_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['aborted1']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,s,k)
    return

def aborted2_activity_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['aborted2']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,s,k)
    return

def aborted3_activity_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['aborted3']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,s,k)
    return

def active_wakelock_data_hook(c,m):
    """
    inputs are current system state
    and matched module gotten from REs['active_wakelock']
    and the summary structure
    and the first part of this function name
    """
    c['active_wakelock'] = m.groups()[0]
    return

def failed_device_data_hook(c,m):
    """
    inputs are current system state
    and matched module gotten from REs['failed_device']
    and the summary structure
    and the first part of this function name
    """
    d = m.groups()[0]
    c['failed_device'] = d
    return

def longest_data_hook(c,m):
    """
    inputs are current system state
    and matched module gotten from REs['longest']
    and the summary structure
    and the first part of this function name
    """
    c['longest_wakelock_name'] = m.groups()[0]
    c['longest_wakelock_len'] = float(m.groups()[1])
    return

def suspended_activity_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['suspended']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,s,k)
    return

def booting_activity_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['booting']
    and the summary structure
    and the first part of this function name
    """
    c['wakeup_wakelock'] = 'bootup'
    c['last_suspend_result'] = suspend_result['BOOTUP']
    c['resume_coulomb'] = 0
    c['activated_coulomb'] = 0
    __state_change_hook(c,s,k)

def wakeup_wakelock_data_hook(c,m):
    """
    inputs are current system state
    and matched module gotten from REs['wakeup_wakelock']
    and the summary structure
    and the first part of this function name
    """
    w = m.groups()[0]
    c['wakeup_wakelock'] = w
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

def resumed_activity_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['resumed']
    and the summary structure
    and the first part of this function name
    """
    c['activated_time'] = __current_time(c)
    __state_change_hook(c,s,k)
    return

def suspend_current_data_hook(c,m):
    w = m.groups()[0]
    c['susp_kicked_coulomb'] = int(w)
    return

def resume_current_data_hook(c,m):
    w = m.groups()[0]
    c['activated_coulomb'] = int(w)
    return

def devicefailed_activity_hook(c,m,s,k):
    __state_change_hook(c,s,k)
    return


# Regular Expressions and Their Handlers End
################################################################################

################################################################################
# State Machine Section Starts
NEXT_STATEs = {
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
        ['resumed',
         ],
    'SUSP_ABORTED':
        ['resumed'
         ],
    'RESUMED':
        ['preparing',
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
         ]
    }
COLLECTING_DATA = {
    'SUSP_KICKED':
        ['suspend_current',
         'longest',
         'failed_device',
         'active_wakelock',
         ],
    'DEVICE_FAILED':
        [
         ],
    'SUSPENDED':
        ['wakeup_wakelock',
         'resume_current',
         'suspend_duration',
         ],
    'SUSP_ABORTED':
        ['active_wakelock',
         ],
    'UNKNOWN':
        ['suspend_current',
         'resume_current',
         'active_wakelock',
         'longest',
         'wakeup_wakelock',
         'suspend_duration',
         'failed_device',
         ],
    'RESUMED':
        [
        ],
    }

def __next_state(c,log):
    """
    Return a three. The first value is next state. 
    The second one is matched regex key.
    The third one is matched result.
    """
    key = None
    matched = None
    for k in ACTIVITIES.keys():
        r,s = ACTIVITIES[k]
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
suspend_result = {
    'UNKNOWN': -1,
    'SUCCESS': 0,
    'ABORTED': 1,
    'DEVICE': 2,
    'BOOTUP': 999
    }

general_state = {
    'UNKNOWN': -1,
    'TRUE': 1,
    'FALSE': 0
    }

def run(fobj_in, fobj_out):
    """ """
    # All stats dict values have following format:
    # (count, duration, cost)
    # The initilization order below is exactly how they are shown in print_sum()
    summary = __init_sum()
    cur_state = __init_cur()
    discharge_stats = dict()

    l = fobj_in.readline()
    while (len(l)):
        t,b = time_and_body(l)
        if t is not None:
            # Check if there's kernel time wrap-up
            if cur_state['kernel_log_start_ts'] < 0:
                cur_state['kernel_log_start_ts'] = float(t)
                cur_state['activated_time'] = float(t)
                cur_state['susp_kicked_time'] = float(t)
                cur_state['resume_time'] = float(t)
            else:
                if float(t) < cur_state['kernel_log_end_ts']:
                    cur_state['kernel_time_wrapup_counter'] += 1
            cur_state['kernel_log_end_ts'] = float(t)
            cur_state['kernel_time_stamp'] = t

            # Use hook function to make statistics and spreadsheet
            k,m = __next_state(cur_state,b)
            if k is not None:
                c = cur_state['state']
                if k not in NEXT_STATEs[c]:
                    __error_print('There might be log missing before%s%s'%
                                  (os.linesep, l))
                if '%s_activity_hook'%k in globals().keys():
                    hook = globals()['%s_activity_hook'%k]
                    hook(cur_state, m, summary, k)
            else:
                k,m =__collect_data(cur_state, b)
                if k:
                    hook = globals()['%s_data_hook'%k]
                    hook(cur_state, m)
        l = fobj_in.readline()
    # This is ugly but necessary: pretending there is a final resumed state, if
    # we're going to enter suspend at the end of the log
    __log_end(cur_state, summary)

    summary['kernel_log_duration'] =\
        __current_time(cur_state) -\
        cur_state['kernel_log_start_ts'] + \
        summary['rtc_stop_time']
    return summary

def print_sum(s):
    try:
        n_active,t_active,c_active = s['session_stats']['active']
    except:
        n_active = 0
        t_active = 0.0000000001
        c_active = 0
    total_cost = c_active
    try:
        n_suspend,t_suspend,c_suspend = s['session_stats']['suspend']
    except:
        n_suspend = 0
        t_suspend = 0.000000001
        c_suspend = 0
    total_cost += c_suspend

    print '=================='
    print 'Suspend Statistics'
    print '=================='
    print '\t'+'Total Duration Covered by The Log (s)\t= %f'%\
        s['kernel_log_duration']

    print '\t'+'Total Active Duration (s)\t\t= %f (%%%.1f)'%\
        (t_active,100*t_active/s['kernel_log_duration'])
    print '\t'+'Total Suspend Duration (s)\t\t= %f (%%%.1f)'%\
        (t_suspend,100*t_suspend/s['kernel_log_duration'])

    print '\t'+'Total Active Session Cost (mAh)\t\t= %.2f (%%%.1f)'%\
        (float(c_active)/1000,100*c_active/total_cost)
    print '\t'+'Total Suspend Session Cost (mAh)\t\t= %.2f (%%%.1f)'%\
        (float(c_suspend)/1000,100*c_suspend/total_cost)

    print '\t'+'Active Session Current Drain\t\t= %f'%\
        (c_active/t_active)
    print '\t'+'Suspend Session Current Drain\t\t= %f'%\
        (c_suspend/t_suspend)
    print os.linesep

    try:
        print '\t'+'Number of times suspend attempted\t= %i (every %.1f s)'%\
            (s['suspend_attempt_counter'],
             s['kernel_log_duration']/s['suspend_attempt_counter'])
    except:
        pass
    try:
        print '\t'+'Number of times device failed\t\t= %i (every %.1f s)'%\
            (s['device_failed_counter'],
             s['kernel_log_duration']/s['device_failed_counter'])
    except:
        pass
    try:
        print '\t'+'Number of times freezing aborted\t= %i (every %.1f s)'%\
            (s['freezing_abort_counter'],
             s['kernel_log_duration']/s['freezing_abort_counter'])
    except:
        pass
    try:
        print '\t'+'Number of total wake-ups\t= %i (every %.1f s)'%\
            (n_suspend,s['kernel_log_duration']/n_suspend)
    except:
        pass
    print os.linesep

    top_count = __init_top(('',0))
    top_duration = __init_top(('',0.0))
    top_cost = __init_top(('',0.0))
    d = s['active_wakelock_stats']
    __find_top(d, top_count, top_duration, top_cost)
    print '===================='
    print 'Freezing Abort Stats'
    print '===================='
    print '\t'+'Top %d failure reasons are:'%TOP
    for i in range(TOP):
        k,v = top_count[i]
        if len(k):
            print '\t\t'+k+': %i'%v
    print '\t'+'Top %d longest failure reasons are:'%TOP
    for i in range(TOP):
        k,v = top_duration[i]
        if len(k):
            print '\t\t'+k+': %f'%v
    print '\t'+'Top %d costly failure reasons are:'%TOP
    for i in range(TOP):
        k,v = top_cost[i]
        if len(k):
            print '\t\t'+k+': %.2f'%(float(v)/1000)
    print os.linesep
    
    top_count = __init_top(('',0))
    top_duration = __init_top(('',0.0))
    top_cost = __init_top(('',0.0))
    d = s['device_failed_stats']
    __find_top(d, top_count, top_duration, top_cost)
    print '===================='
    print 'Device Failure Stats'
    print '===================='
    print '\t'+'Top %d failed devices are:'%TOP
    for i in range(TOP):
        k,v = top_count[i]
        if len(k):
            print '\t\t'+k+': %i'%v
    print '\t'+'Top %d longest device failures are:'%TOP
    for i in range(TOP):
        k,v = top_duration[i]
        if len(k):
            print '\t\t'+k+': %f'%v
    print '\t'+'Top %d costly device failures are:'%TOP
    for i in range(TOP):
        k,v = top_cost[i]
        if len(k):
            print '\t\t'+k+': %.2f'%(float(v)/1000)
    print os.linesep

    top_count = __init_top(('',0))
    top_duration = __init_top(('',0.0))
    top_cost = __init_top(('',0.0))
    d = s['wakeup_wakelock_stats']
    __find_top(d, top_count, top_duration, top_cost)
    print '=================='
    print 'Wakeups'
    print '=================='
    print '\t'+'Top %d wakeup wakelocks are:'%TOP
    for i in range(TOP):
        k,v = top_count[i]
        if len(k):
            print '\t\t%s: %i'%(k,v)
    print '\t'+'Top %d longest wakeup wakelocks are:'%TOP
    for i in range(TOP):
        k,v = top_duration[i]
        if len(k):
            print '\t\t%s: %f'%(k,v)
    print '\t'+'Top %d costly wakeup wakelocks are:'%TOP
    for i in range(TOP):
        k,v = top_cost[i]
        if len(k):
            print '\t\t%s: %.2f'%(k,float(v)/1000)
    print os.linesep

    top_count = __init_top(('',0))
    top_duration = __init_top(('',0.0))
    top_cost = __init_top(('',0.0))
    d = s['longest_wakelock_stats']
    __find_top(d, top_count, top_duration, top_cost)
    print '=================='
    print 'Wakelocks'
    print '=================='
    print 'Top %d suspend blockers:'%TOP
    for i in range(TOP):
        k,v = top_count[i]
        if len(k):
            print '\t\t%s: %d'%(k,v)
#    print 'Top %d costly suspend blockers:'%TOP
#    for i in range(TOP):
#        k,v = top_cost[i]
#        if len(k):
#            print '\t\t%s: %f'%(k,v)
    print 'Top %d longest suspend blockers:'%TOP
    for i in range(TOP):
        k,v = top_duration[i]
        if len(k):
            print '\t\t%s: %f'%(k,v)

    print 'Top %d longest blocking wakelock instances:'%TOP
    d = s['top_longest_blocking_wakelock']
    for i in range(TOP):
        e,l = d[i]
        print '\t'+'%d ended at %s'%(l,e)
#    print 'Top %d costly suspend blocking sessions:'%TOP
#    for i in range(TOP):
#        c,s,e = s['top_costly_blocking_session']
#        print '\t'+'%d mC\t\tfrom %s to %s'%(c,s,e)
#    print 'Top %d longest suspend blocking sessions:'%TOP
#    d = s['top_longest_blocking_session']
#    for i in range(TOP):
#        e,l = d[i]
#        print '\t'+'%f \t\t until %s'%(l,e)
    print os.linesep

    print '=================='
    print 'Suspend Sessions'
    print '=================='
    print '\t'+'Top %d costly suspend sessions:'%TOP
    d = s['top_costly_suspend_session']
    for i in range(TOP):
        e,l = d[i]
        print '\t'+'%.2f mAh\t\tended at %s mA'%(float(l)/1000, e)
    print os.linesep

    print '\t'+'Top %d longest suspend sessions:'%TOP
    d = s['top_longest_suspend_session']
    for i in range(TOP):
        e,l = d[i]
        print '\t'+'%d \t\tended at %s'%(l,e)
    print os.linesep

    print '=================='
    print 'Active Sessions'
    print '=================='
    print '\t'+'Top %d costly active sessions:'%TOP
    d = s['top_costly_active_session']
    for i in range(TOP):
        e,l = d[i]
        print '\t'+'%.2f mAh\t\t ended at %s mA'%(float(l)/1000,e)
    print os.linesep

    print '\t'+'Top %d longest active sessions:'%TOP
    d = s['top_longest_active_session']
    for i in range(TOP):
        e,l = d[i]
        print '\t'+'%d \t\t ended at %s'%(l,e)
    print os.linesep

    print '=================='
    print 'Wakeup Sessions'
    print '=================='
    print '\t'+'Top %d costly wakeup sessions:'%TOP
    d = s['top_costly_wakeup_session']
    i = 0
    while(i < 5):
        e,l = d[i]
        print '\t'+'%.2f mAh\t\t ended at %s mA'%(float(l)/1000,e)
        i += 1
    print os.linesep

    print '\t'+'Top %d longest wakeup sessions:'%TOP
    d = s['top_longest_wakeup_session']
    for i in range(TOP):
        e,l = d[i]
        print '\t'+'%d \t\t ended at %s'%(l,e)
    print os.linesep

    print '=================='
    print 'Display On'
    print '=================='
    print 'Coming Soon'
    # display-on total time
    # display-on total cost
    # display-on longest top n
    # display-on costly top n
    print os.linesep

    print '=================='
    print 'Charging'
    print '=================='
    print 'Coming Soon'
    # charging total time

if __name__ == "__main__":
    sys.stderr.write(SOFTWARE_NAME+' '+LAST_UPDATE+os.linesep)
    sys.stderr.write(AUTHOR+os.linesep)

    if len(sys.argv) < 2:
        __usage()

    fobj_in = None
    fobj_out = None
    try:
        fobj_in = open(sys.argv[1], 'r')
        fobj_out = open(sys.argv[1]+'.csv', 'w')
    except Exception as e:
        __error_print('Opening input or output file'+
                      os.linesep + e)
        if fobj_in:
            fobj_in.close()
        sys.exit(1)

    s = run(fobj_in, fobj_out)
    print_sum(s)

    fobj_out.close()
    fobj_in.close()
# Main Sections Ends
################################################################################
