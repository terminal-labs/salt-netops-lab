import time
from salt.utils.platform import is_proxy

__virtualname__ = 'net_config'


def __virtual__():
    proxytype = __pillar__.get('proxy', {}).get('proxytype')
    device_type = __pillar__.get('proxy', {}).get('device_type')
    if is_proxy() and proxytype == 'netmiko' and device_type == 'cisco_nxos':
        return __virtualname__
    return False


def load(template, session_name=None):
    if not session_name:
        session_name = "config-session-" + str(int(time.time() * 1000))
    config_session_cmd = 'configure session ' + session_name

    device_output = __salt__['netmiko.send_config'](
        config_file=template,
        config_mode_command=config_session_cmd,
        delay_factor=2,
        exit_config_mode=True
    )

    if 'Invalid' in device_output:
        return {
            'result': False,
            'session_name': session_name,
            'device_output': device_output
        }
    return {
        'result': True,
        'session_name': session_name,
        'device_output': device_output
    }


def diff(session):
    return "diff not supported on cisco_nxos"


def commit(session):
    cfg_session_cmd = 'configure session ' + session
    ret = ""
    ret += __salt__['netmiko.send_config'](
        config_commands=['commit'], config_mode_command=cfg_session_cmd, exit_config_mode=True
    )
    return ret


def abort(session):
    cfg_session_cmd = 'configure session ' + session
    ret = ""
    ret += __salt__['netmiko.send_config'](
        config_commands=['abort'], config_mode_command=cfg_session_cmd, exit_config_mode=True
    )
    return ret
