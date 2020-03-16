# Salt NetOps Lab

## Lab 2: Writing Custom Execution Modules

Let’s create a module which abstracts the exact method for communicating across proxy device types that we can commonly call upon when configuring devices. Create a file in the `_modules` directory in the `file_roots` named `common.py`

```
# /srv/salt/_modules/common.py

def send_config(template):
    proxytype = __pillar__.get("proxy", {}).get("proxytype")

    if proxytype == 'netmiko':
        return __salt__['netmiko.send_config'](
            config_file=template, delay_factor=5
        )
    elif proxytype == 'junos':
        return __salt__['junos.load'](template, format='set')
    else:
        raise ValueError("Unsupported proxytype: {0}".format(proxytype))
```

This simple abstraction lets us use one function for configuration across our proxy minion types.

Let’s try it. First, make sure to sync the modules:

```
$ salt \* saltutil.sync_modules
```

Then, we can target all proxy minions.

```
$ salt \* common.send_config salt://templates/basic.j2
```

Or exclude the normal salt minion from the target (targeting only proxy minions):

```
$ salt -I 'proxy:*' common.send_config salt://templates/basic.j2
```

This example uses `common.send_config` to abstract the communication method per proxytype and the jinja within basic.j2 to send the appropriate configuration per device type.

This is easy enough. However, there is an alternative way of doing this, which is intrinsic to salt. This concept is known as _virtual modules_.

__Background__

Salt is intended to run on many platforms and devices. Thus, salt must obtain information about its platform in order to know which modules it can run. This is the reason grains exist. We can leverage this in our own custom modules, just like how salt does in its many built-in functions. 

Although somewhat trivial, let’s see how we would achieve the same result as the above `common.py` module, but this time using _virtual_ modules. 

```
# /srv/salt/_modules/common_netmiko.py

import salt.utils.platform

__virtualname__ = 'common'

def __virtual__():
    proxytype = __pillar__.get('proxy', {}).get('proxytype')
    if salt.utils.platform.is_proxy() and proxytype == 'netmiko':
        return __virtualname__
    return False

def send_config(template):
    return __salt__['netmiko.send_config'](
        config_file=template, delay_factor=4
    )
```

```
# /srv/salt/_modules/common_junos.py

import salt.utils.platform

__virtualname__ = 'common'

def __virtual__():
    proxytype = __pillar__.get('proxy', {}).get('proxytype')
    if salt.utils.platform.is_proxy() and proxytype == 'junos':
        return __virtualname__
    return False

def send_config(template):
    return __salt__['junos.load'](template, format='set')
```

Let’s try to understand what’s happening here. Salt modules which contain a `__virtual__` function indicate to salt whether the module will be “loaded” or not. If it is to be loaded on the minion, this function returns `True`, and `False` otherwise. Furthermore, if we wish to alias the functional name we must use the `__virtualname__` global variable. This must be returned by `__virtual__` if the module is to be loaded.

To test this, remember to delete the original `common.py`

```
$ rm common.py
```

And clear the cache and sync the modules (`saltutil.clear_cache` is needed to remove the old module)

```
$ salt \* saltutil.clear_cache
$ salt \* saltutil.sync_all
```

```
$ salt \* common.send_config salt://templates/basic.j2
```

You should see that now the correct method of implementation has been achieved through the use of salt’s virtual modules. This was notably a trivial example use case for virtual modules; feel free to use the former method if it is more appropriate for your specific application. However, as modules grow and device communication diverges, virtual modules can be a useful tool for code organization and abstraction.

__Another example virtual module: `get`__

Let’s create a virtual module for “getting” various device information, for example a running configuration. The syntax we hope to achieve will be as follows:

```
$ salt \* get.running_config
```

Let’s see how to create this for the running config function example. Create the following custom module for the netmiko proxy minions.

```
# /srv/salt/_modules/get_netmiko.py

from salt.utils.platform import is_proxy

__virtualname__ = 'get'

def __virtual__():
    proxytype = __pillar__.get('proxy', {}).get('proxytype')
    if is_proxy() and proxytype == 'netmiko':
        return __virtualname__
    return False

def running_config():
    return __salt__['netmiko.send_command']('show running-config')
```

And do something similar for junos proxy minions

```
# /srv/salt/_modules/get_junos.py

from salt.utils.platform import is_proxy

__virtualname__ = 'get'

def __virtual__():
    proxytype = __pillar__.get('proxy', {}).get('proxytype')
    if is_proxy() and proxytype == 'junos':
        return __virtualname__
    return False

def running_config():
    return \
        __salt__['junos.rpc']('get-config')['rpc_reply']['configuration']
```

Now we can use the same function to get the configuration across all of our device types. As always, remember to sync your modules first!

```
$ salt \* saltutil.sync_all
$ salt -L <minion1>,<minion2>,<minion3> get.running_config
```

Notice the above use of the `-L` flag for targeting a _list_ of minions.

We will use this get module again in Lab 4 when we learn about salt runners and orchestration.

__Extra: Custom module to expose proxy__

Often the proxy minion will utilize a device-specific api. This is the case with the junos proxy. Juniper maintains this library for specific interaction with its devices. While salt already exposes certain functions in the junos api proxy, in this section we will create a module which will allow us to generalize it. It will also illustrate how we can extend salt to create custom modules which utilize the `__proxy__` global variable.

```
# /srv/salt/_modules/juniper.py

import salt.utils.platform

__virtualname__ = 'junos'

def __virtual__():
    proxytype = __pillar__.get('proxy', {}).get('proxytype')
    if salt.utils.platform.is_proxy() and proxytype == 'junos':
        return __virtualname__
    return False

def call(*args, **kwargs):
    conn = __proxy__['junos.conn']()
    fn = getattr(conn, args[0])
    args = args[1:]    

    # remove salt added private kwargs
    kwargs_pub = {}
    for kwarg in kwargs:
        if not kwarg.startswith("_"):
            kwargs_pub[kwarg] = kwargs[kwarg]

    return fn(*args, **kwargs_pub)
```

Remember to sync modules:

```
$ salt \* saltutil.sync_modules
```

Now we have the ability to call any method on the proxy connection object with arguments and / or keyword arguments, directly from the command line. For example:

```
$ salt -I 'proxy:proxytype:junos' junos.call cli 'show version'
```

It’s also good to realize that using “junos” as the virtualname in the above function did not overwrite any of the built-in in “junos” functions; it simply added “call” to the already existing junos functions, for junos proxy minions, as seen with the following command:

```
$ salt \* sys.list_functions junos
```

To clarify, the result from the example above using our custom junos.call function could have been achieved with the __built-in__ `junos.cli` function.

```
$ salt -I 'proxy:proxytype:junos' junos.cli 'show version'
```

_However_, the goal of this exercise was to demonstrate how to create a function which exposes the underlying device api using the proxy minion’s open connection via the `__proxy__` object.

## Lab 3: Build Custom State Modules With Custom Execution Modules

__Background__

Salt _state_ modules are of great use in ensuring that our devices are in a known, predictable state. States modules are written in an idempotent fashion to achieve reliability and repeatability regardless of the initial state of the system.

Salt has many built-in state modules. These modules are different than the execution modules we have seen previously. One key difference is that they typically aren’t run directly from the command line, rather, they are used within sls files. This is because the namespace of the cli is the execution module namespace. For example,

```
$ salt \* pkg.install vim
```

`pkg` is referencing the _execution_ module namespace, whereas

```
$ salt \* pkg.installed vim
```

will fail since `pkg.installed` is a _state_ module function. The workaround we could use is to pass the _state_ module we wish to execute to the `state.single` _execution_ module.

```
$ salt \* state.single pkg.installed name=vim
```

Often, state modules will call a primitive execution module, wrapping it with idempotent logic and forming the required return data. For example, we can install software packages with the execution module `pkg.install`, yet we can determine if a package is installed with the `pkg.installed` state module and install it if necessary. Let’s see what that looks like.

We can install the package [jq](https://stedolan.github.io/jq/) with the following salt command. Target the master’s minion; or we can use `salt-call` instead for convenience.

```
$ salt-call pkg.install jq
```

So, now the `jq` package is installed. Go ahead and make a directory called “states” with a simple sls file which makes use of `pkg.installed`.

```
$ mkdir states
```

```
# /srv/salt/states/install_jq.sls

install_jq_pkg:
  pkg.installed:
    - name: jq
```

And we can apply this state with:

```
$ salt-call state.apply states.install_jq
```

We will see that the state module will inform us that the package has already been installed, thus the state is successful. Let’s remove the package and view the difference when re-apply the state.

```
$ salt-call pkg.remove jq
```

```
$ salt-call state.apply states.install_jq
```

The jq package gets installed now that it wasn’t already and the return data indicates this change!

This is a trivial example since most package managers handle idempotency already. (A repeated command to install jq won’t install it twice, rather it will notify it was already installed). However, the philosophy behind the separation of behavior for execution module and state module is a powerful one, and increasingly useful as we attempt to deploy configuration across our vast infrastructure, when at times, we may not know the state of our devices / system.

Following this logic, it may be useful, before applying a configuration, to determine whether a configuration _should_ be applied. Another example is to check whether there is a difference, “diff”, in the proposed configuration and current configuration.

__Writing custom state modules__

We can write custom state modules similarly to how we built custom execution modules. We store them in a `_states` directory in our `file_roots`. However, salt has an opinionated form for the return data from state modules. The return must conform to the following structure.

```
# form of state module return data:

# must be a dictionary with the following keys:
# ['name', 'result', 'comment', 'changes']

ret = {
    'name': name,     # name will always be passed as 1st arg
    'result': None,   # True for success, False for failure, None for test
    'changes': {},    # must be a dictionary, typ. {'old': ..., 'new': ...}
    'comment': '',    # any other info may be included here
}
```

As you’ve seen with the `install_jq` state above. The return (shown below) corresponds with the return dictionary keys explained in this section.

```
local:
----------
      ID: install_jq_package
    Function: pkg.installed
        Name: jq
      Result: True
     Comment: All specified packages are already installed
     Started: 20:17:14.577174
    Duration: 815.882 ms
     Changes:

Summary for local
------------
Succeeded: 1
Failed:    0
------------
Total states run:     1
Total run time: 815.882 ms
```

Salt is opinionated about the state module’s return data. The  `name`, `result`, `changes`, and `comment` keys must appear and no other keys may be present.

__Name:__

Take a look at the example sls below.

```
# apache.sls

apache2:
  pkg.installed

manage_apache_conf:
  file.managed:
    - name: /etc/apache2/apache2.conf
    - source: salt://files/apache2.conf
    - require:
      - apache2
```

`name` is always passed by the salt state system as the first argument to a state module function. If "name" is not explicitly specified, the id of the block will be passed in as the name. In the first block of the sls file, this would be “apache2”. The name parameter can be used by the module or disregarded. The “name” key must still appear in the return dictionary.

__Result:__

`result` indicates to the state system whether the state was a success or failure. The output will be colored green for success, and red for failure at the cli. Furthermore, the value here is used by the requisite system to determine if dependent modules should be executed.

General guidelines:
* Return `True` if the state was successful or the minion was already in the desired state
* Return `False` if the module failed to achieve the desired state
* Return `None` if no changes were made, i.e. test mode

A common paradigm in salt state modules is to allow a `test=True` keyword argument to be passed when running the state with `state.apply`, `state.sls`, etc. This variable can be accessed within the module with  `__opts__["test"]`. This is useful to attempt to indicate what changes _would_ be applied before actually running the state. 

__Changes:__

Changes are somewhat self explanatory however common convention is to describe changes, if any, with a dictionary of the following form:

```
ret['changes'] = {
    'old': ...,
    'new': ...,
}
```

With `...` being some sort of description of the old and new state of the system. The “changes” key is important, because this is also used by the requisite system, e.g. with the “onchanges” flag. If there is any data except an empty dictionary, None, False, or other like object, changes will be reported by salt.

__Comment:__

Comment is the most self-explanatory and the least opinionated. Put any further details you would like to include here.

### State Module Example: `configured`

Our goal in this lab is to create a state module to ensure our devices are configured with the correct templates. We want this state to display idempotency and ideally be able to run against all devices, regardless of device type, version, or manufacturer. We will adhere to salt best practice, and also add the test flag functionality, when possible. 

__Start with sls__

It is often helpful to view how the sls will look before starting to write the function itself. Consider the following (no need to create this file).

```
# example.sls

configure_switch_router:
  net_config.configured:
    - name: salt://templates/arista/arista_eos_igmp.j2
```

__Building Blocks are Execution Modules__

Execution modules are able to be used within state or execution modules through the use of the `__salt__` dunder dictionary. As stated previously, it’s important to realize that execution modules are the only modules available at the cli, while state modules are the only ones available within sls files. (There are workarounds to having an execution module run in an sls file, but it is not common or preferred). It is good programming practice to have the execution modules be small atomic self contained operations, whereas state modules can be long and complex accounting for the many different scenarios, implementing idempotent logic, and forming the return dictionary.

Following this practice, instead of making a single execution module to “configure” the device, we will instead make several functions performing the common steps along the way of configuring the device. Hopefully, by the end you will realize the benefit of this approach. We will be able to reuse these small execution modules in many ways at the cli and within our custom state module.

There are several operations that happen when “configuring” a device. The task can be separated as follows:

* Load
** Loading the candidate configuration
* Diff
** Obtaining a diff of the candidate configuration and the running configuration
* Commit
** Commiting the candidate configuration as the running configuration
* Abort
** Discarding the candidate configuration

Let’s create a custom _virtual_ execution module `net_config` to perform these tasks. Starting with arista, let’s create `net_config_arista.py` and include the appropriate virtual function.

```
# /srv/salt/_modules/net_config_arista.py
from salt.utils.platform import is_proxy


__virtualname__ = 'net_config'

def __virtual__():
    proxytype = __pillar__.get('proxy', {}).get('proxytype')
    device_type = __pillar__.get('proxy', {}).get('device_type')
    if is_proxy() and proxytype == 'netmiko' \
        and device_type == 'arista_eos':
        return __virtualname__
    return False

def load(template, session_name=None):
    pass

def diff(session):
    pass

def commit(session):
    pass

def abort(session):
    pass
```

Let's start with the load function.

```
...
import time
from jinja2 import TemplateError
...

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
```

This function will render a template, create a configuration session, and load the candidate configuration. It will also return the result of the operation, as well as the device interaction and other information that may be needed later, such as the session name used.
 
Let’s move to the diff function.

```
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
    og_config = \
        [line.rstrip() for line in orig_config if not line.startswith('!')]

    session_return = __salt__['netmiko.send_command'](
        'show session-config named ' + session + ' | no-more',
        delay_factor=4
    ).splitlines()
    new_config = \
        [line.rstrip() for line in session_return \
         if not line.startswith('!')]
    return '\n'.join(set(new_config).symmetric_difference(set(og_config)))
```

This function is a bit simpler. It probes the device for the running configuration and the session configuration, determines the diff, and returns the result.

Now for the commit and abort functions.

```
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
```

These functions are also self explanatory, commiting / aborting the configuration session, respectively.

Now sync the modules:

```
$ salt \* saltutil.sync_all
```

We will need some templates to apply, so create the arista directory with the following templates.

```
mkdir /srv/salt/templates/arista
```

__/srv/salt/templates/arista/add_vlan_10.j2__:
```
vlan 10
name lab-demo-example-vlan
```

__/srv/salt/templates/arista/rm_vlan_10.j2
```
no vlan 10
```

These templates are inverse of each other and will be helpful for testing our functions.

And we are ready to test! This module will only work for the arista proxy minion, so target that one.

__Example Use:__

```
bash-4.4# salt -I 'proxy:device_type:arista_eos' \
          net_config.load salt://templates/arista/add_vlan_10.j2
arista_minion_id:
    ----------
    device_output:
            vlan 10
            name lab-demo-example
            lab-rack362-s52-2(config-s-config-vlan-10)#name lab-demo-example
            lab-rack362-s52-2(config-s-config-vlan-10)#end
            lab-rack362-s52-2#
    result:
            True
    session_name:
            config-session-1580320170306
```

Now we can use the `session_name` to check the diff.

```
$ salt -I 'proxy:device_type:arista_eos' \
  net_config.diff config-session-1580320170306
```

The above command will show differences between the running and proposed configuration, if any. To commit,

```
$ salt -I 'proxy:device_type:arista_eos' \
  net_config.commit config-session-1580320170306

```

Or if you wish to _abort_ the configuration session, you can use the abort function.

```
$ salt -I 'proxy:device_type:arista_eos' \
  net_config.abort config-session-1580320170306
```

Play around with the different templates, viewing the diff, and aborting / committing as necessary.

_Can you think of ways we can improve the above functions?_

________________________________________________________________

__Do it!__

Create a `net_config` virtual module for the other device types we have (juniper and cisco) and expose the same 4 functions as above. The `net_config_juniper` module should be a bit easier than `net_config_arista`, since junos exposes many of these methods via its api. Remember you can list the functions available in the junos module with the following command:

```
$ salt -I 'proxy:proxytype:junos' sys.list_functions junos
```

Also, notice that cisco has only slightly different behavior as arista, in part due to it also being operated by a netmiko proxy minion. Only slight modification to `net_config_arista.py` should be necessary to create `net_config_cisco.py`

After attempting it on your own, download / compare your solution vs. the solution located [here](https://github.com/terminal-labs/salt-netops-lab/tree/master/srv-salt/_modules).  You should end up with three files for the virtualized `net_config` module, `net_config_arista.py`, `net_config_juniper.py`, and `net_config_cisco.py`.

```
$ wget https://raw.githubusercontent.com/terminal-labs/salt-netops-lab/master/srv-salt/_modules/net_config_cisco.py -O /srv/salt/_modules/net_config_cisco.py
```

```
$ wget https://raw.githubusercontent.com/terminal-labs/salt-netops-lab/master/srv-salt/_modules/net_config_juniper.py -O /srv/salt/_modules/net_config_juniper.py
```

And then, sync the modules.

```
$ salt \* saltutil.sync_modules
```

After syncing the new modules, we can use these functions freely at the cli!  Test the newly added virtual modules with the following templates for cisco and juniper.

__/srv/salt/templates/cisco/add_test_access_list.j2__
```
ip access-list test-access-list
permit tcp any any
```

__/srv/salt/templates/cisco/rm_test_access_list.j2__
```
no ip access-list test-access-list
```

__/srv/salt/templates/juniper/lldp.set__
```
set protocols lldp interface all
```

__/srv/salt/templates/juniper/no_lldp.set__
```
delete protocols lldp interface all
```

We now have a very robust virtualized config module for our 3 device types!

Now, if we want to use them in states we should create the corresponding custom state module. 

### Writing the custom state module function `net_config.configured`

As mentioned earlier, it is of great benefit to include idempotent logic when writing state modules. We will be using the `net_config` execution module we just created to build our state module.

Create a new directory, “_states”, and inside make a new file named `net_config.py`. We’ll use what we learned previously for writing state modules. 

```
$ mkdir _states
```

```
# /srv/salt/_states/net_config.py

def configured(name):
    """
    Ensure the device is configured. Uses config execution module
    """
    ret = {
        'name': name,
        'result': None,
        'changes': {},
        'comment': '',
    }

    load_ret = __salt__['net_config.load'](name)
    session_name = load_ret.get('session_name')
    
    # junos doesn't use session_name
    if session_name:
        diff = __salt__['net_config.diff'](session_name)
    else:
        diff = __salt__['net_config.diff']()

    if not diff:
        ret['result'] = True
        ret['comment'] = "The device is already configured."
        
        # abort session
        abort_ret = __salt__['net_config.abort'](session_name) if \
            session_name else __salt__['net_config.abort']()

        return ret
    elif __opts__["test"]:
        # there is a diff, but test=True
        ret['result'] = None
        ret['changes'] = {'diff': diff}
        ret['comment'] = "Changes would be applied but we are "\
            "in test mode"


        # abort session
        abort_ret = __salt__['net_config.abort'](session_name) if \
            session_name else __salt__['net_config.abort']()

        return ret
    else:
        # there is a diff and we are not in test mode
        if session_name:
            commit_ret = __salt__['net_config.commit'](session_name)
        else:
            commit_ret = __salt__['net_config.commit']()
        ret['result'] = True
        ret['changes'] = {'old': '', 'new': diff} 
        ret['comment'] = "The device has been successfully configured."
        return ret
```

This state is salty and idempotent. Notice that we achieved our abstraction at the execution module level, using virtual modules for `net_config` selecting for the proxy and device type. This fits well for this use case, however, we _could_ have applied the same virtual abstraction at the state module level.

_Can you see ways in which the above state module can be improved?_

Now let’s sync our modules and states:

```
$ salt \* saltutil.sync_all
```

Almost ready to test! Let’s create an sls file which will be used for all of our devices configuration. Create the following in the “states” directory.

```
# /srv/salt/states/configure_devices.sls

{%- if pillar['proxy']['proxytype'] == 'junos' %}
  {%- set template_path = "salt://templates/juniper/lldp.set" %}
{%- elif 'arista' in pillar['proxy']['device_type'] %}
  {%- set template_path = "salt://templates/arista/add_vlan_10.j2" %}
{%- elif 'cisco' in pillar['proxy']['device_type'] %}
  {%- set template_path = "salt://templates/cisco/add_test_access_list.j2" %}
{% endif %}

configure_device:
  net_config.configured:
    - name: {{ template_path }}
```

Here we are using the state function we just made, and applying the appropriate template_path. Notice how we are using the power of jinja and salt’s inject global variables to dynamically determine the appropriate template path!

Now let’s execute this state with the following command. Target all the proxy minions.

```
$ salt -I 'proxy:*' state.sls states.configure_devices
```

Notice the output coloration upon success, changes, etc. We now have a powerful salt configuration state!

Notice the state’s idempotency. We can apply the same state again and will expect no perturbation since we are already in our desired configuration.

```
$ salt -I 'proxy:*' state.sls states.configure_devices
```

Success! Note that since cisco_nxos has no diff functionality, this device will not display idempotency and will apply the configuration again regardless of if there is a diff. 

We can apply a “de-configuration” state to further test and demonstrate. Create the following.

```
# /srv/salt/states/deconfigure_devices.sls

{%- if pillar.proxy.proxytype == 'junos' %}
  {%- set template_path = "salt://templates/juniper/no_lldp.set" %}
{%- elif 'arista' in pillar.proxy.device_type %}
  {%- set template_path = "salt://templates/arista/rm_vlan_10.j2" %}
{%- elif 'cisco' in pillar.proxy.device_type %}
  {%- set template_path = "salt://templates/cisco/rm_test_access_list.j2" %}
{% endif %}

deconfigure_devices:
  net_config.configured:
    - name: {{ template_path }}
```

And now apply this template, but first use the test flag.

```
$ salt -I 'proxy:*' state.sls states.deconfigure_devices test=True
```

Cool! Notice how the output is yellow if changes were going to be made if we _weren’t_ in test mode.

Now let’s actually apply the deconfiguration.

```
$ salt -I 'proxy:*' state.sls states.deconfigure_devices
```

Success!

## Lab 4: Runners and Orchestration

__Background__

Salt operates as a publish / subscribe model, i.e., the master publishes events to its event bus on port 4505, while the minions, listening to this port, determine if the job is for them and proceed to execute it. The minion will then return data on port 4506. Therefore, minus the publishing of events, the salt minion is largely responsible for the successful completion and return of the job. However, salt provides a mechanism for which to execute commands on the master, these are called runners.

There are many runners built into salt. For example, to view values from the master config:

```
$ salt-run config.get file_roots
base:
  - /srv/salt
  - /srv/spm/salt
```

View the master event bus:

```
$ salt-run state.event pretty=True
```

Send an event to the master event bus:

```
$ salt-run event.send my/custom/event '{"foo": "bar"}'
```

We can also write our own runner modules!

__Writing a Custom Runner__

To do this we need to first declare where we are going to store the runner modules. Write the following to the master config (`/etc/salt/master`) .

```
runner_dirs:
  - /srv/runners
  - /srv/salt/runners
```

Remember to restart the master process after modifying the config.

```
$ supervisorctl restart salt-master
```

Be sure to also create the corresponding directories.

```
$ mkdir /srv/runners && mkdir /srv/salt/runners
```

Runner modules are always executed on the master, so they can be especially useful for “one-off” scripts. Adding a runner module instead of normal python utility scripts allows us to use typical salt paradigms _and_ freely use them within salt states and orchestration.

Let’s see how we can create a runner module which includes a function to generate a report of the running configuration across our minions. Create the following file in our runner directory.

```
# /srv/salt/runners/generate.py

import json
import os

def running_config_report(tgt='*', tgt_type='glob', save_as=''):
    """
    Generate a report of the running configuration on the targeted minions
    Args:
        tgt: target
        tgt_type: target type, e.g. list, glob, etc.
        save_as: optional filename to save report as
    Returns:
        report of minion configuration
    """
    minions_ret = __salt__['salt.execute'](
        tgt, 'get.running_config', tgt_type=tgt_type
    )

    report = "The following is the minion's running configuration: \n\n"
    for minion in minions_ret:
        report += "{0}: \n\n".format(minion)

        running_config = minions_ret[minion]
        if isinstance(running_config, dict):
            running_config = json.dumps(running_config, indent=2)
        report += running_config
        
        report += '\n\n'
    report += "End of report.\n"

    if save_as:
        path, filename = os.path.split(save_as)
        if not os.path.isdir(path):
            os.makedirs(path)
        with open(save_as, 'w') as file_:
            file_.write(report)
        return "Running config report saved to: {0}".format(save_as)

    return report
```

Notice we are using the `get.running_config` function we created earlier through the use of the `salt.execute` built-in runner. Also, notice that we took advantage of `salt.execute` which publishes the job for the targeted minions to execute in parallel. Then, we simply iterate through the return to generate the report.

Now we can execute this function on a list of minions with a command like the following:

```
$ salt-run generate.running_config_report \
    tgt='["<minion1>","<minion2>",...]' tgt_type=list
```

And we get a report of the running configuration from our list of minions!

__Salt Orchestration__

Salt orchestration is a framework for executing states from the perspective of the master. Orchestration states are written similar to normal sls files and are typically stored in a folder “orch” in the `file_roots` directory (though this is not required). For example:

```
$ salt-run state.orch orch.my_orch_state
```

_What differentiates orchestration from normal state application and why would we want to use it?_

Orchestration shares many similarities with normal state application, but it is always executed on the master. (Notice there isn’t a target in the above command). The sls files can contain any state module function as we are used to. The real reason to use orchestration instead of a simple salt state is when an ordered execution of states must happen sequentially across many _different_ physical devices (minions). 

One example could be a deployment of template configurations, where one set of configurations must be applied on one target group before the application of another set of configurations on a _different_ target group. 

Create the “orch” directory and the following orchestration state sls file.

```
$ mkdir /srv/salt/orch
```

```
# /srv/salt/orch/sequential_config.sls

configure_cisco:
  salt.state:
    - tgt: 'proxy:device_type:cisco*'
    - tgt_type: pillar
    - sls:
      - states.configure_devices

configure_juniper:
  salt.state:
    - tgt: 'proxy:proxytype:junos'
    - tgt_type: pillar
    - sls:
      - states.configure_devices
    - require:
      - configure_cisco

configure_arista:
  salt.state:
    - tgt: 'proxy:device_type:arista*'
    - tgt_type: pillar
    - sls:
      - states.configure_devices
    - require:
      - configure_juniper

generate_running_config_report:
  salt.runner:
    - name: generate.running_config_report
    - tgt: 'proxy:*'
    - tgt_type: pillar
    - save_as: /var/tmp/running_config_report.log
    - onchanges:
      - configure_cisco
      - configure_juniper
      - configure_arista
```

Watch the master event bus as this orchestration executes. Notice how this orchestration makes use of salt’s requisite system. We make use of our `generate` runner module and only run it when there are changes in the configuration states.

```
$ salt-run state.event pretty=True
```

```
$ salt-run state.orch orch.sequential_config
```

Congratulations! We have successfully sequentially configured our devices with salt orchestration, with requisites, _and_ generated a report of the running configuration with our custom runner!

## Lab 5: Reactor and Beacons

Salt has the ability to automate infrastructure operations with little to no human intervention. In this lab, we will become familiar with the salt reactor and beacons. Beacons are salt modules that are distributed and run on the minion, which can be configured to emit messages when certain conditions occur. Examples include file modification, memory usage exceeding a threshold, a package being out of date, etc. Salt has many built-in beacon modules which only require minimal configuration to set up. Additionally, we could write a custom beacon, or a stand-alone python script which emits salt events.

The salt reactor is located on the master and _reacts_ to events. These reactions can respond to events emitted by beacons (or custom scripts). Once the event tag is matched, salt will execute a list of reactor sls files, typically to remediate or otherwise respond to the event in question. Events can pass data to be used by reactors. This can be very useful in certain scenarios.

__Writing a custom beacon__

A beacon module is simply a function that runs on a set interval. Many of the normal salt module paradigms hold for beacon modules however, there are specific guidelines.

Beacon modules:
 * Must contain a function called `beacon`
   * This is the function that gets called every interval
   * This function is passed the configuration as an argument
   * Must return a list of dictionaries
     * Each element of the list corresponds to an event and the contents of the dictionary is passed as the event data
* _Optionally_ include a function called `validate`
  * Used to validate the configuration passed to the beacon
  * Called once upon initialization
* _Custom_ beacon modules are stored in the `_beacons` directory in `file_roots`

Let’s get started writing a custom beacon. This custom beacon will take a list of salt execution modules, with optional arguments, and return its data as an event. This can be seen as a general purpose beacon but we will use it to detect configuration drift. Once we configure our reactor we will automatically remediate the configuration drift.

```
$ mkdir /srv/salt/_beacons
```

```
# /srv/salt/_beacons/monitor.py

def validate(config):
    _config = {}
    map(_config.update, config)
    
    for fun in _config['salt_fun']:
        if fun not in __salt__:
            return False, "{0} not in __salt__".format(fun)
    return True, "valid config"

def beacon(config):
    events = []
    _config = {}
    map(_config.update, config)

    for fun in _config['salt_fun']:
        ret = __salt__[fun]()
        if ret:
            events.append({'salt_fun': fun, 'ret': ret})
    return events

```

As simple as that we have our first custom beacon! Remember the `validate` function is called once when salt loads the beacon. This function is optional, however, here it is validating that the functions we have listed are present within the `__salt__` dunder, i.e loaded by the salt minion. The `beacon` function is simply looping through the functions provided in the config and returning the output. Remember the return of the `beacon` function is a list of dictionaries; each list item is one salt event’s data.

To test this beacon create the following configuration

```
# /etc/salt/minion.d/beacons.conf

beacons:
  monitor:
    - salt_fun:
      - test.version
    - interval: 30  # seconds

```

Under `salt_fun` we can put as many salt functions as we like, just be sure we have enough time to execute them within our beacon interval. Notice the `interval` keyword. This is built-in to the beacon system and requires no configuration within our custom beacon. Salt will execute this module once every beacon interval.

Sync the beacons and restart the minion process.

```
$ salt \* saltutil.sync_beacons
$ supervisorctl restart salt-minion
```

Now let’s watch the master event bus for the beacon event and return data.

```
$ salt-run state.event pretty=True
```

We should see the beacon event tag `salt/beacon/<minion-id>/monitor` with the return data every 30 seconds!  This is good for confirming the functionality of the beacon, but at scale, checking daily would be more practical.

If things aren’t working correctly consult the minion logs.

```
$ tail -f /var/log/salt/minion
```

Or for proxy minions

```
$ tail -f /var/log/salt/proxy
```

You can download a more extensive version of this beacon on the terminal labs repo [here](https://github.com/terminal-labs/salt-netops-lab/blob/master/srv-salt/_beacons/monitor.py)

This modified version will accept `args` and `kwargs` for the salt functions listed to be executed. __Note: the above _simplified_ beacon will suffice for this demo__

Let’s make more use of this beacon. We normally check configuration drift by hand. But what if we could _monitor configuration drift automatically_ and _auto-remediate_ it? 

Let’s do it! 

First let’s make an execution module function that will actually detect the drift. Luckily, we already have the building blocks in place in `net_config_arista.py`, `net_config_juniper.py`, and `net_config_cisco.py`.

Add the following.

```
# /srv/salt/_modules/net_config_arista.py

...

def drift(template):
    """
    Check if there is drift and abort session
    """
    load_ret = load(
        template, 
        session_name="check-drift-{0}".format(int(time.time() * 1000))
    )
    diff_ret = diff(load_ret['session_name'])
    if diff_ret:
        ret = True
    else:
          ret = False
    abort_ret = abort(load_ret['session_name'])
    return ret
```

```
# /srv/salt/_modules/net_config_juniper.py

...

def drift(template):
    load_ret = load(template)
    diff_ret = diff()
    if diff_ret:
        ret = True
    else:
          ret = False
    abort_ret = abort()
    return ret
```

Cisco NXOS has no support for drift so we can disregard.

```
# /srv/salt/_modules/net_config_cisco.py

...

def drift(template):
    return False

```

Make sure you sync the modules!

```
$ salt \* saltutil.sync_modules
```

Let’s test it!

```
$ salt -I 'proxy:device_type:arista_eos' net_config.drift salt://templates/arista/add_vlan_10.j2
```

Our drift function will return `True` if there is drift from the template given, and `False` otherwise.

Let’s now use this function with our beacon to determine if there is configuration drift every beacon interval and report an event, if so.

Since we cannot give separate configurations for proxy minions located on the same machine we won’t be able to send different configuration templates per device. To get around this inconvenience, we can write a `default_config` datum in pillar which will be used by our drift function if the template argument is omitted. __Note: Normal salt minions and and native salt minions would not suffer from this inconvenience.__

See the following changes to the drift function below:

```
# /srv/salt/_modules/net_config_arista.py

...

def drift(template=''):
    """
    Check if there is drift and abort session
    """
    if not template:
        template = __pillar__['default_config']

    load_ret = load(
        template, 
        session_name="check-drift-{0}".format(int(time.time() * 1000))
    )
    diff_ret = diff(load_ret['session_name'])
    if diff_ret:
        ret = True
    else:
          ret = False
    abort_ret = abort(load_ret['session_name'])
    return ret
```

```
# /srv/salt/_modules/net_config_juniper.py

...

def drift(template=''):
    if not template:
          template = __pillar__['default_config']
    load_ret = load(template)
    diff_ret = diff()
    if diff_ret:
        ret = True
    else:
          ret = False
    abort_ret = abort()
    return ret
```

```
# /srv/salt/_modules/net_config_cisco.py

...

def drift(template=''):
    return False
```

Additionally, we need to add the `default_config` pillar for our devices. Find your devices in `/srv/pillar/top.sls` and add an additional sls entry. 

For example, create a file `/srv/pillar/arista/default_config.sls`

```
default_config: salt://templates/arista/add_vlan_10.j2
```

Add assign this to your minion in top:

```
base:
  ...
  'my-minion-id':
    - arista/proxy-minion-data
    - arista/default_config
```

Do this for all your proxy minions.

The default_config pillar file should be the following for juniper and cisco, respectively.

__/srv/pillar/juniper/default_config.sls__
```
default_config: salt://templates/juniper/lldp.set
```

__/srv/pillar/cisco/default_config.sls__
```
default_config: salt://templates/cisco/add_test_access_list.j2
```

Make sure you apply these files to the appropriate minion in `top.sls` as done in the example arista minion above.

We’re almost ready to set up our beacon! Re-sync the modules and refresh the pillar.

```
$ salt \* saltutil.sync_all
$ salt \* saltutil.refresh_pillar
```

Now let’s add our beacon configuration. Since we’re configuring our proxy minions, this will go in `/etc/salt/proxy`.

```
# /etc/salt/proxy
...

beacons:
  monitor: 
    - salt_fun:
      - net_config.drift
    - interval: 30
    - disable_during_state_run: True
```

The `disable_during_state_run` option is a built-in beacon feature which will, as its name implies, halt the beacon during state module execution. This is to help avoid potential interference with other operations.

Be sure to restart the proxy minions and then view the salt event bus.

```
supervisorctl restart <minion1> <minion2> <minion3>
```

```
$ salt-run state.event pretty=True
```

Play around intentionally perturbing the configuration to test whether the beacon is working correctly. Use the `configure_devices` and `deconfigure_devices` states we created earlier.

```
$ salt -I 'proxy:*' state.sls states.configure_devices
```

```
$ salt -I 'proxy:*' state.sls states.deconfigure_devices
```

You should be seeing the beacon event after “de-configuring” the device.

Now let’s add auto-remediation via salt reactor.

In the master config file we can set up our reactor to watch for event tags:

```
# /etc/salt/master
...

reactor:
  - salt/beacon/*/monitor/:
    - /srv/salt/reactor/remediate_monitor.sls
```

Notice that we can include the glob “*” in the event tag. For each event of this form the master sees, the list of reactor states will be executed. Here we have only listed a single reactor state that we have yet to write. Let’s write it.

```
$ mkdir /srv/salt/reactor
```

```
# /srv/salt/reactor/remediate_monitor.sls

configure_device_{{ data['_stamp'] }}:
  local.state.sls:
    - tgt: {{ data['id'] }}
    - args:
      - mods:
        - states.configure_devices
```

The syntax for reactor states is different from other sls files you have seen before. The difference is that the namespace for the function in the id block (in this case `local.state.sls`) must designate which type of reactor is run. “Local” will run an execution module on the remote minions specified. “Runner” will allow us to use runner modules. Other types of reactors exist. For more information, please consult the [docs page on reactor states](https://docs.saltstack.com/en/latest/topics/reactor/).

Restart the master and view the event. “Deconfigure” the minions, if necessary, to view the auto-remediation.

```
$ supervisorctl restart salt-master
```

```
$ salt-run state.event pretty=True
```

You should now be able to see the auto-remediation of the device’s configuration drift!

Note: If the monitor beacon we set up earlier for the normal salt minion is still running (executing test.version) we will have a reactor state run occur, according to our current configuration. There are several ways to prevent this from happening, however, the easiest for our purposes is to disable the beacon for this minion. We can do this with the following:

```
$ mv /etc/salt/minion.d/beacons.conf \
    /etc/salt/minion.d/beacons.conf.disabled
$ supervisorctl restart salt-minion
```

Congratulations! We have learned a powerful way to auto-remediate configuration drift!
