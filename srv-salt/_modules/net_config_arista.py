# /srv/salt/_modules/net_config_arista.py
import time

from salt.utils.platform import is_proxy

__virtualname__ = 'net_config'

def __virtual__():
    proxytype = __pillar__.get('proxy', {}).get('proxytype')
    device_type = __pillar__.get('proxy', {}).get('device_type')
    if is_proxy() and proxytype == 'netmiko' and device_type == 'arista_eos':
        return __virtualname__
    return False

def load(template, session_name=None):
    """
    Load a configuration template with a given session name.
    If session_name is None (default) a unique string will be generated.

    Args:
        template: template config path
        session_name: unique string for session
    Returns:
        Dictionary with 'result', 'session_name', and 'device_output' keys
    """
    if not session_name:
        session_name = "config-session-" + str(int(time.time() * 1000))
    config_session_cmd = 'configure session ' + session_name

    device_output = __salt__['netmiko.send_config'](
        config_file=template,
        config_mode_command=config_session_cmd,
        delay_factor=2,
        exit_config_mode=True
    )

    if 'Invalid input' in device_output:
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
    """
    Determine if there is a diff between the running-config
    and session-config given by session

    Args:
        session: name of session to compare for diff
    Return:
        diff or None
    """
    orig_config = __salt__['netmiko.send_command'](
        'show running-config | no-more'
    ).splitlines()
    og_config = [line.rstrip() for line in orig_config if not line.startswith('!')]

    session_return = __salt__['netmiko.send_command'](
        'show session-config named ' + session + ' | no-more',
        delay_factor=4
    ).splitlines()
    new_config = [line.rstrip() for line in session_return if not line.startswith('!')]
    return '\n'.join(set(new_config).symmetric_difference(set(og_config)))

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
