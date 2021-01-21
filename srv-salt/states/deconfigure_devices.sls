# /srv/salt/states/deconfigure_devices.sls

{%- if pillar.proxy.proxytype == 'junos' %}
  {%- set template_path = "salt://templates/juniper/no_igmp.set" %}
{%- elif 'arista' in pillar.proxy.device_type %}
  {%- set template_path = "salt://templates/arista/rm_vlan_10.j2" %}
{%- elif 'cisco' in pillar.proxy.device_type %}
  {%- set template_path = "salt://templates/cisco/rm_test_access_list.j2" %}
{% endif %}

deconfigure_devices:
  network.configured:
    - name: {{ template_path }}
