#!/usr/bin/env python
#
# Copyright 2018 VMware, Inc.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING,
# BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''TODO
author: Rahul Raghuvanshi
'''

EXAMPLES = '''
- nsxt_uplink_profiles:
      hostname: "10.192.167.137"
      username: "admin"
      password: "Admin!23Admin"
      validate_certs: False
'''

RETURN = '''# '''


import json, time
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.vmware import vmware_argument_spec, request
from ansible.module_utils._text import to_native

def get_profile_params(args=None):
    args_to_remove = ['state', 'username', 'password', 'port', 'hostname', 'validate_certs']
    for key in args_to_remove:
        args.pop(key, None)
    for key, value in args.copy().items():
        if value == None:
            args.pop(key, None)
    return args

def get_host_switch_profiles(module, manager_url, mgr_username, mgr_password, validate_certs):
    try:
      (rc, resp) = request(manager_url+ '/host-switch-profiles', headers=dict(Accept='application/json'),
                      url_username=mgr_username, url_password=mgr_password, validate_certs=validate_certs, ignore_errors=True)
    except Exception as err:
      module.fail_json(msg='Error accessing host profiles. Error [%s]' % (to_native(err)))
    return resp

def get_uplink_profile_from_display_name(module, manager_url, mgr_username, mgr_password, validate_certs, display_name):
    host_switch_profiles = get_host_switch_profiles(module, manager_url, mgr_username, mgr_password, validate_certs)
    for host_switch_profile in host_switch_profiles['results']:
        if host_switch_profile.__contains__('display_name') and host_switch_profile['display_name'] == display_name:
            return host_switch_profile
    return None

def check_for_update(module, manager_url, mgr_username, mgr_password, validate_certs, profile_params):
    existing_profile = get_uplink_profile_from_display_name(module, manager_url, mgr_username, mgr_password, validate_certs, profile_params['display_name'])
    if existing_profile is None:
        return False
    if existing_profile.__contains__('mtu') and profile_params.__contains__('mtu') and \
        existing_profile['mtu'] != profile_params['mtu']:
        return True
    if existing_profile.__contains__('transport_vlan') and profile_params.__contains__('transport_vlan') and \
        existing_profile['transport_vlan'] != profile_params['transport_vlan']:
        return True
    return False

def main():
  argument_spec = vmware_argument_spec()
  argument_spec.update(display_name=dict(required=True, type='str'),
                        mtu=dict(required=False, type='int'),
                        teaming=dict(required=True, type='dict',
                        name=dict(required=True, type='str'),
                        policy=dict(required=True, type='str'),
                        standby_list=dict(required=False, type='list'),
                        active_list=dict(required=True, type='list')),
                        transport_vlan=dict(required=False, type='int'),
                        named_teamings=dict(required=False, type='list'),
                        lags=dict(required=False, type='list'),
                        resource_type=dict(required=True, type='str', choices=['UplinkHostSwitchProfile']),
                        state=dict(reauired=True, choices=['present', 'absent']))

  module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
  profile_params = get_profile_params(module.params.copy())
  state = module.params['state']
  mgr_hostname = module.params['hostname']
  mgr_username = module.params['username']
  mgr_password = module.params['password']
  validate_certs = module.params['validate_certs']
  display_name = module.params['display_name']
  manager_url = 'https://{}/api/v1'.format(mgr_hostname)

  host_switch_profile_dict = get_uplink_profile_from_display_name (module, manager_url, mgr_username, mgr_password, validate_certs, display_name)
  host_switch_profile_id, revision = None, None
  if host_switch_profile_dict:
    host_switch_profile_id = host_switch_profile_dict['id']
    revision = host_switch_profile_dict['_revision']

  if state == 'present':
    headers = dict(Accept="application/json")
    headers['Content-Type'] = 'application/json'
    updated = check_for_update(module, manager_url, mgr_username, mgr_password, validate_certs, profile_params)

    if not updated:
      # add the block
      if module.check_mode:
          module.exit_json(changed=True, debug_out=str(json.dumps(profile_params)), id='12345')
      request_data = json.dumps(profile_params)
      try:
          if host_switch_profile_id:
              module.exit_json(changed=False, id=host_switch_profile_id, message="Uplink profile with display_name %s already exist."% module.params['display_name'])

          (rc, resp) = request(manager_url+ '/host-switch-profiles', data=request_data, headers=headers, method='POST',
                                url_username=mgr_username, url_password=mgr_password, validate_certs=validate_certs, ignore_errors=True)
      except Exception as err:
          module.fail_json(msg="Failed to add host profile. Request body [%s]. Error[%s]." % (request_data, to_native(err)))

      time.sleep(5)
      module.exit_json(changed=True, id=resp["id"], body= str(resp), message="host profile with display name %s created." % module.params['display_name'])
    else:
      if module.check_mode:
          module.exit_json(changed=True, debug_out=str(json.dumps(profile_params)), id=host_switch_profile_id)

      profile_params['_revision'] = revision # update current revision
      request_data = json.dumps(profile_params)
      id = host_switch_profile_id
      try:
          (rc, resp) = request(manager_url+ '/host-switch-profiles/%s' % id, data=request_data, headers=headers, method='PUT',
                                url_username=mgr_username, url_password=mgr_password, validate_certs=validate_certs, ignore_errors=True)
      except Exception as err:
          module.fail_json(msg="Failed to update host profile with id %s. Request body [%s]. Error[%s]." % (id, request_data, to_native(err)))

      time.sleep(5)
      module.exit_json(changed=True, id=resp["id"], body= str(resp), message="host profile with id %s updated." % id)

  elif state == 'absent':
    # delete the array
    id = host_switch_profile_id
    if id is None:
        module.exit_json(changed=False, msg='No host switch profile exist with display name %s' % display_name)
    if module.check_mode:
        module.exit_json(changed=True, debug_out=str(json.dumps(profile_params)), id=id)
    try:
        (rc, resp) = request(manager_url + "/host-switch-profiles/%s" % id, method='DELETE',
                              url_username=mgr_username, url_password=mgr_password, validate_certs=validate_certs)
    except Exception as err:
        module.fail_json(msg="Failed to delete host profile with id %s. Error[%s]." % (id, to_native(err)))

    time.sleep(5)
    module.exit_json(changed=True, object_name=id, message="host profile with id %s deleted." % id)


if __name__ == '__main__':
    main()
