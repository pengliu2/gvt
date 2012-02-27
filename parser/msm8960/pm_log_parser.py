import string,os,re,sys

################################################################################
# The Functions to be called when state changes
def __add_onto_elem_in_dict(d, k, v):
    if k in d.keys():
        v0,v1,v2 = d[k]
        d[k] = (v[0]+v0, v[1]+v1, v[2]+v2)
    else:
        d[k] = v

def __susp_kicked_hook(c,s):
    c['state'] = 'SUSP_KICKED'
    return 

def __susp_aborted_hook(c,s):
    s['freezing_abort_counter'] += 1
    c['this_suspend_result'] = suspend_result['ABORTED']
    c['state'] = 'SUSP_ABORTED'

    # This would be the attempted time
    c['this_attempt_time'] = c['kernel_log_end_ts'] + \
        KERNEL_TIME_LIMIT * \
        c['kernel_time_wrapup_counter']
    return

def __device_failed_hook(c,s):
    c['state'] = 'DEVICE_FAILED'
    s['device_failed_counter'] += 1
    c['this_suspend_result'] = suspend_result['DEVICE']

    # Update time stamps
    c['this_attempt_time'] = c['kernel_log_end_ts'] + \
        KERNEL_TIME_LIMIT * \
        c['kernel_time_wrapup_counter']
    return

def __suspended_hook(c,s):
    c['state'] = 'SUSPENDED'
    s['suspend_success_counter'] += 1
    c['this_suspend_result'] = suspend_result['SUCCESS']
    # If there's no coulomb log, we use this for suspend time
    if c['last_attempt_coulomb'] < 0:
        c['this_attempt_time'] = c['kernel_log_end_ts'] + \
            KERNEL_TIME_LIMIT * \
            c['kernel_time_wrapup_counter']
    return

def __res_kicked_hook(c,s):
    c['state'] = 'RES_KICKED'
    return

def __resumed_hook(c,s):
    # Add the duration, count and cost to the active period before this suspend
    ta = c['this_attempt_time'] - c['last_activated_time']
    s['total_active_duration'] += ta
    if c['last_suspend_result'] == suspend_result['SUCCESS']:
        __add_onto_elem_in_dict(
            s['wakeup_wakelock_stats'],
            c['last_wakeup_wakelock'],
            (1,
             ta,
             0
             )
            )
    else:
        if c['last_suspend_result'] == suspend_result['ABORTED']:
            __add_onto_elem_in_dict(
                s['active_wakelock_stats'],
                c['last_active_wakelock'],
                (1, # added to counter
                 ta, # added to time counter
                 0  # added to cost counter
                 )
                )
        elif c['last_suspend_result'] == suspend_result['DEVICE']:
            __add_onto_elem_in_dict(
                s['device_failed_stats'],
                c['last_failed_device'],
                (1,
                 ta,
                 0
                 )
                )
        else:
            __error_print("Unknown suspend result")

    # update cur_state
    c['state'] = 'RESUMED'
    if c['last_suspend_result'] != suspend_result['BOOTUP']:
        s['suspend_attempt_counter'] += 1
    # If there's no coulomb log, we use this for activated time
    # TODO: following line should also be in POWER CONSUMPTION
    # this time suspend duration
    if c['this_activated_coulomb'] < 0:
        current_time = c['kernel_log_end_ts'] + KERNEL_TIME_LIMIT *\
            c['kernel_time_wrapup_counter']
    else:
        current_time = c['this_activated_time']
    ts = current_time - c['this_attempt_time']

    if c['this_suspend_result'] == suspend_result['SUCCESS']:
        s['total_suspend_duration'] += ts
        c['last_wakeup_wakelock'] = c['this_wakeup_wakelock']
        c['this_wakeup_wakelock'] = 'UNKNOWN'
    else:
        s['total_active_duration'] += ts

    c['last_suspend_result'] = c['this_suspend_result']
    c['last_activated_time'] = current_time
    c['last_activated_coulomb'] = c['this_activated_coulomb']
    c['this_activated_time'] = -1.0
    c['this_activated_coulomb'] = -1.0
    c['this_suspend_result'] = 'UNKNOWN'
    # TODO: should write into the spreadsheet file as well
    return
# The Functions to be called when state changes
################################################################################

################################################################################
# Regular Expressions and Their Handlers
REs = {
    'f1': (re.compile('Freezing user space processes ...'),
           'SUSP_KICKED'
           ),
    'f2': (re.compile('Freezing remaining freezable tasks ...'),
           'SUSP_KICKED'
           ),
    'a1': (re.compile('Freezing of tasks  aborted'),
           'SUSP_ABORTED'
           ),
    'a2': (re.compile('Freezing of user space  aborted'),
           'SUSP_ABORTED'
           ),
    'a3': (re.compile('active wake lock ([^,]+),*'),
           None
           ),
    'd1': (re.compile('PM: Device ([^ ]+) failed to suspend'),
           'DEVICE_FAILED'
           ),
    's0': (re.compile('RESERVED FOR POWER CONSUMPTION'),
           None
           ),
    's1': (re.compile('msm_pm_enter: power collapse'),
           'SUSPENDED'
           ),
    's2': (re.compile('RESERVED FOR POWER STATE'),
           None
           ),
    'w0': (re.compile('Booting Linux'),
           'RESUMED'
           ),
    'w1': (re.compile('msm_pm_enter: return'),
           'RES_KICKED'
           ),
    'w2': (re.compile('wakeup wake lock: (\w+)'),
           'RES_KICKED'
           ),
    'w3': (re.compile('RESERVED FOR POWER CONSUMPTION'),
           None
           ),
    'w4': (re.compile('suspend: exit suspend, ret = [^ ]+ \((\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{9}) UTC\)'),
           'RESUMED'
           )
}
def __state_change_hook(c,s,k):
    r,state = REs[k]
    x_name = string.lower("__%s_hook"%state)
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
        __resumed_hook(c, s)
    elif state == 'RESUMED':
        ta = c['kernel_log_end_ts'] - c['last_activated_time']
        s['total_active_duration'] += ta
        __add_onto_elem_in_dict(
            s['wakeup_wakelock_stats'],
            c['last_wakeup_wakelock'],
            (1,
             ta,
             0
             )
            )

def f1_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['f1']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,s,k)
    return 

def f2_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['f2']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,s,k)
    return

def a1_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['a1']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,s,k)
    return

def a2_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['a2']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,s,k)
    return

def a3_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['a3']
    and the summary structure
    and the first part of this function name
    """
    if c['state'] == 'UNKNOWN':
        c['last_active_wakelock'] = m.groups()[0]
        return
    if (c['state'] == 'SUSP_KICKED'):
        c['last_active_wakelock'] = m.groups()[0]
    __state_change_hook(c,s,k)
    return

def d1_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['d1']
    and the summary structure
    and the first part of this function name
    """
    d = m.groups()[0]
    c['last_failed_device'] = d
    __state_change_hook(c,s,k)
    return

def s1_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['s1']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,s,k)
    return

def s2_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['s2']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,m,s,k)
    return

def w0_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['w0']
    and the summary structure
    and the first part of this function name
    """
    c['this_wakeup_wakelock'] = 'bootup'
    c['last_suspend_result'] = suspend_result['BOOTUP']
    __state_change_hook(c,s,k)

def w1_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['w1']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,s,k)
    return

def w2_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['w2']
    and the summary structure
    and the first part of this function name
    """
    w = m.groups()[0]
    c['this_wakeup_wakelock'] = w
    __state_change_hook(c,s,k)
    return

def w3_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['w3']
    and the summary structure
    and the first part of this function name
    """
    pass

def w4_hook(c,m,s,k):
    """
    inputs are current system state
    and matched module gotten from REs['w4']
    and the summary structure
    and the first part of this function name
    """
    __state_change_hook(c,s,k)
    return
# Regular Expressions and Their Handlers End
################################################################################

################################################################################
# State Machine Section Starts
NEXT_STATEs = {
    'SUSP_KICKED':
        ['SUSP_ABORTED',
         'DEVICE_FAILED',
         'SUSPENDED'
         ],
    'SUSP_ABORTED':
        ['RESUMED'
         ],
    'DEVICE_FAILED':
        ['RESUMED'
         ],
    'SUSPENDED':
        ['RES_KICKED'
         ],
    'RES_KICKED':
        ['RESUMED'
         ],
    'RESUMED':
        ['SUSP_KICKED'
         ],
    'UNKNOWN':
        ['RESUMED',
         'RES_KICKED',
         'SUSPENDED',
         'DEVICE_FAILED',
         'SUSP_ABORTED',
         'SUSP_KICKED'
         ]
    }

def __next_state(log):
    """
    Return a three. The first value is next state. 
    The second one is matched regex key.
    The third one is matched result.
    """
    state = None
    key = None
    matched = None
    for k in REs.keys():
        r,s = REs[k]
        m = r.match(log) # I will compare search and match later here
        if m is not None:
            state = s
            matched = m
            key = k
            break
    return state,key,matched

# State Machine Section Ends
################################################################################
################################################################################
# Log Processing Section Starts
KERNEL_TIME_LIMIT = 131072
KERNEL_TIME_STAMP =\
    re.compile('^<\d>\[ *(\d+)\.(\d+)\] (.*)')
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
# Helpers Section Starts
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
# Helpers Sections Ends
################################################################################

################################################################################
# Main Section Starts
suspend_result = {
    'SUCCESS': 0,
    'ABORTED': 1,
    'DEVICE': 2,
    'BOOTUP': 999
    }

def run(fobj_in, fobj_out):
    """ """
    # All stats dict values have following format:
    # (count, duration, cost)
    summary = dict()
    summary['suspend_success_counter'] = 0
    summary['wakeup_source_stats'] = dict()
    summary['wakeup_wakelock_stats'] = dict()

    summary['device_failed_counter'] = 0
    summary['device_failed_stats'] = dict()

    summary['freezing_abort_counter'] = 0
    summary['active_wakelock_stats'] = dict()

    summary['total_suspend_duration'] = 0
    summary['total_active_duration'] = 0
    summary['suspend_attempt_counter'] = 0

    summary['kernel_log_duration'] = 0

    cur_state = dict()
    cur_state['state'] = 'UNKNOWN'
    # We record following values when the phone attempts to enter suspend
    cur_state['this_attempt_time'] = -1.0
    cur_state['last_attempt_coulomb'] = -1.0
    cur_state['last_suspend_result'] = suspend_result['SUCCESS']
    cur_state['this_suspend_result'] = suspend_result['SUCCESS']
    cur_state['last_activated_coulomb'] = -1.0
    cur_state['last_activated_time'] = -1.0
    # When last attempt suspended the phone successfully
    cur_state['last_wakeup_wakelock'] = 'UNKNOWN'
    cur_state['last_wakeup_source'] = 'UNKNOWN'
    cur_state['last_activated_time'] = -1.0
    # When last attempt failed because of device
    cur_state['last_failed_device'] = 'UNKNOWN'
    cur_state['last_failed_time'] = -1.0
    # When last attempt failed because of wakelock
    cur_state['last_active_wakelock'] = 'UNKNOWN'
    cur_state['last_abort_time'] = -1.0

    cur_state['this_activated_time'] = -1.0
    cur_state['this_activated_coulomb'] = -1.0
    cur_state['this_wakeup_wakelock'] = 'UNKNOWN'

    cur_state['kernel_log_start_ts'] = -1.0
    cur_state['kernel_log_end_ts'] = 0.0
    cur_state['kernel_time_wrapup_counter'] = 0

    l = fobj_in.readline()
    while (len(l)):
        t,b = time_and_body(l)
        if t is not None:
            # Check if there's kernel time wrap-up
            if cur_state['kernel_log_start_ts'] < 0:
                cur_state['kernel_log_start_ts'] = float(t)
                cur_state['last_activated_time'] = float(t)
                cur_state['this_attempt_time'] = float(t)
                cur_state['last_activated_time'] = float(t)
                cur_state['last_failed_time'] = float(t)
                cur_state['last_abort_time'] = float(t)
            else:
                if float(t) < cur_state['kernel_log_end_ts']:
                    cur_state['kernel_time_wrapup_counter'] += 1
            cur_state['kernel_log_end_ts'] = float(t)

            # Use hook function to make statistics and spreadsheet
            s,k,m = __next_state(b)
            if k is not None:
                c = cur_state['state']
                if s is not None and s not in NEXT_STATEs[c]:
                    # We have to handle log missing here
                    pass
                hook = globals()['%s_hook'%k]
                hook(cur_state, m, summary, k)
        l = fobj_in.readline()
    # This is ugly but necessary: pretending there is a final resumed state, if
    # we're going to enter suspend at the end of the log
    __log_end(cur_state, summary)

    summary['kernel_log_duration'] =\
        cur_state['kernel_time_wrapup_counter']*KERNEL_TIME_LIMIT-\
        cur_state['kernel_log_start_ts'] +\
        cur_state['kernel_log_end_ts']
    __debug_print(summary)
    return summary

def __init_top_5(t, v):
    for i in range(5):
        t.append(v)
    return

def __place_value(k, v, t):
    i = 0
    while (i < 5):
        t1,t2 = t[i]
        if v > t2:
            break
        i += 1

    if i < 5:
        t.insert(i, (k,v))
    return t[0:5]
    

def __find_top_5(d, t1, t2, t3):
    for k in d.keys():
        v1,v2,v3 = d[k]
        __place_value(k,v1,t1)
        __place_value(k,v2,t2)
        __place_value(k,v3,t3)

def print_summary(s):
    print '=================='
    print 'Suspend Statistics'
    print '=================='
    print '\t'+'Total Duration Covered by The Log (s)\t= %f'%\
        s['kernel_log_duration']
    print '\t'+'Number of times suspend attempted\t= %i'%\
        s['suspend_attempt_counter']
    print '\t'+'Number of times device failed\t\t= %i'%\
        s['device_failed_counter']
    print '\t'+'Number of times freezing aborted\t= %i'%\
        s['freezing_abort_counter']
    print '\t'+'Number of times suspend successful\t= %i'%\
        s['suspend_success_counter']
    print '\t'+'Total Suspend Duration (s)\t\t= %f'%\
        s['total_suspend_duration']
    print '\t'+'Total Active Duration (s)\t\t= %f'%\
        s['total_active_duration']
    print os.linesep

    top_count = list()
    top_duration = list()
    top_cost = list()
    __init_top_5(top_count,('',0))
    __init_top_5(top_duration,('',0.0))
    __init_top_5(top_cost,('',0.0))
    d = s['active_wakelock_stats']
    __find_top_5(d, top_count, top_duration, top_cost)
    print '===================='
    print 'Freezing Abort Stats'
    print '===================='
    print '\t'+'Top 5 failure reasons are:'
    for i in range(5):
        k,v = top_count[i]
        if len(k):
            print '\t\t'+k+': %i'%v
    print '\t'+'Top 5 longest failure reasons are:'
    for i in range(5):
        k,v = top_duration[i]
        if len(k):
            print '\t\t'+k+': %f'%v
    print os.linesep

    top_count = list()
    top_duration = list()
    top_cost = list()
    __init_top_5(top_count,('',0))
    __init_top_5(top_duration,('',0.0))
    __init_top_5(top_cost,('',0.0))
    d = s['device_failed_stats']
    __find_top_5(d, top_count, top_duration, top_cost)
    print '===================='
    print 'Device Failure Stats'
    print '===================='
    print '\t'+'Top 5 failed devices are:'
    for i in range(5):
        k,v = top_count[i]
        if len(k):
            print '\t\t'+k+': %i'%v
    print '\t'+'Top 5 longest device failures are:'
    for i in range(5):
        k,v = top_duration[i]
        if len(k):
            print '\t\t'+k+': %f'%v

    top_count = list()
    top_duration = list()
    top_cost = list()
    __init_top_5(top_count,('',0))
    __init_top_5(top_duration,('',0.0))
    __init_top_5(top_cost,('',0.0))
    d = s['wakeup_wakelock_stats']
    __find_top_5(d, top_count, top_duration, top_cost)
    print '=================='
    print 'Wakeups'
    print '=================='
    print '\t'+'Top 5 wakeup wakelocks are:'
    for i in range(5):
        k,v = top_count[i]
        if len(k):
            print '\t\t%s: %i'%(k,v)
    print '\t'+'Top 5 longest wakeup wakelocks are:'
    for i in range(5):
        k,v = top_duration[i]
        if len(k):
            print '\t\t%s: %f'%(k,v)
    print os.linesep

    print '=================='
    print 'Wakelocks'
    print '=================='
    print '\t'+'Top 5 costly suspend blockers are:'
    print '\t'+'Top 5 longest suspend blockers are:'
    print '\t'+'Top 5 costly wakeup sessions are because of:'
    print '\t'+'Top 5 longest wakeup sessions are because of:'
    print os.linesep

SOFTWARE_NAME = 'log parser'
AUTHOR = 'Peng Liu - <a22543@motorola.com>'
LAST_UPDATE = 'Dec 06, 2011'

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
    print_summary(s)

    fobj_out.close()
    fobj_in.close()
# Main Sections Ends
################################################################################
