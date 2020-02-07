# /srv/salt/states/configure_devices.sls

{%- if pillar['proxy']['proxytype'] == 'junos' %}
  {%- set template_path = "salt://templates/juniper/lldp.set" %}
{%- elif 'arista' in pillar['proxy']['device_type'] %}
  {%- set template_path = "salt://templates/arista/add_vlan_10.j2" %}
{%- elif 'cisco' in pillar['proxy']['device_type'] %}
  {%- set template_path = "salt://templates/cisco/add_test_access_list.j2" %}
{% endif %}

configure_device:
  network.configured:
    - name: {{ template_path }}
