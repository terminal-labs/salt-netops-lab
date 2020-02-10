import time
from jinja2 import TemplateError

from salt.utils.platform import is_proxy

__virtualname__ = 'config'


def __virtual__():
    proxytype = __pillar__.get('proxy', {}).get('proxytype')
    device_type = __pillar__.get('proxy', {}).get('device_type')
    if is_proxy() and proxytype == 'netmiko' and device_type == 'arista_eos':
        return __virtualname__
    return False


def load(template, session_name=None):
    if not session_name:
        session_name = "config-session-" + str(int(time.time() * 1000))
    config_session_cmd = 'configure session ' + session_name

    template_string = __salt__['slsutil.renderer'](
        template, default_renderer='jinja'
    ).strip()
    list_of_commands = template_string.splitlines()
    if not list_of_commands:
        raise TemplateError(
            "The rendered template contains 0 lines of configuration. "\
            "Check the template or the template authorization."
        )

    __salt__['netmiko.enter_config_mode'](
        config_command=config_session_cmd
    )
    device_output = __salt__['netmiko.send_config'](
        config_commands=list_of_commands,
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
    return '\n'.join(set(new_config) - set(og_config))


def commit(session):
    cfg_session_cmd = 'configure session ' + session
    ret = ""
    ret += __salt__['netmiko.enter_config_mode'](
        config_command=cfg_session_cmd
    )
    ret += __salt__['netmiko.send_config'](
        config_commands=['commit'], exit_config_mode=True
    )
    return ret


def abort(session):
    cfg_session_cmd = 'configure session ' + session
    ret = ""
    ret += __salt__['netmiko.enter_config_mode'](
        config_command=cfg_session_cmd
    )
    ret += __salt__['netmiko.send_config'](
        config_commands=['abort'], exit_config_mode=True
    )
    return ret
