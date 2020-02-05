"""
Beacon to monitor minion.
Intentionally general.
Specify 'salt' function you wish to monitor and report data

Example config:

beacons:
  monitor:
    - salt_fun:
      - slsutil.renderer:
          args:
            - salt://states/apache.sls
          kwargs:
            - default_renderer: jinja
      - test.ping
    - interval: 3600 # seconds
"""
import logging

LOG = logging.getLogger(__name__)

def _parse_args(args_kwargs_dict):
    args = args_kwargs_dict.get('args', [])
    kwargs = args_kwargs_dict.get('kwargs', {})
    if kwargs:
        _kwargs = {}
        map(_kwargs.update, kwargs)
        kwargs = _kwargs

    return args, kwargs


def validate(config):
    _config = {}
    map(_config.update, config)

    for entry in _config['salt_fun']:
        if isinstance(entry, dict):
            LOG.debug(entry)
            # check dict is of correct form
            fun, args_kwargs_dict = entry.items()[0]
            for key in args_kwargs_dict.keys():
                if key == 'args':
                    if not isinstance(args_kwargs_dict[key], list):
                        return False, "args key for fun {0} must be list".format(fun)
                elif key == 'kwargs':
                    if not isinstance(args_kwargs_dict[key], list):
                        return False, "kwargs key for fun {0} must be list of key value pairs".format(fun)
                    for key_value in args_kwargs_dict[key]:
                        if not isinstance(key_value, dict):
                            return False, "{0} is not a key / value pair".format(key_value)
                else:
                    return False, "key {0} not allowed under fun {1}".format(key, fun)
        else:
            # entry must be function itself
            fun = entry

        if fun not in __salt__:
            return False, "{0} not in __salt__".format(fun)

    return True, "valid config"


def beacon(config):
    events = []
    _config = {}
    map(_config.update, config)

    for entry in _config['salt_fun']:
        if isinstance(entry, dict):
            fun, args_kwargs_dict = entry.items()[0]
            args, kwargs = _parse_args(args_kwargs_dict)
        else:
            fun = entry
            args = ()
            kwargs = {}

        ret = __salt__[fun](*args, **kwargs)

        if ret:
            _ret = {'salt_fun': fun, 'ret': ret}
            if args:
                _ret['args'] = args
            if kwargs:
                _ret['kwargs'] = kwargs
            events.append(_ret)
    return events
