# -*- coding: utf-8 -*-
import fauxfactory
import pytest

from cfme import test_requirements
from cfme.rest.gen_data import a_provider as _a_provider
from cfme.rest.gen_data import vm as _vm
from cfme.utils import error
from cfme.utils.blockers import BZ
from cfme.utils.rest import (
    assert_response,
    delete_resources_from_collection,
    query_resource_attributes,
)
from cfme.utils.wait import wait_for


pytestmark = [test_requirements.provision]


@pytest.fixture(scope='function')
def a_provider(request):
    return _a_provider(request)


@pytest.fixture(scope='function')
def vm(request, a_provider, appliance):
    vm_name = _vm(request, a_provider, appliance.rest_api)
    return appliance.rest_api.collections.vms.get(name=vm_name)


@pytest.mark.tier(3)
def test_query_vm_attributes(vm, soft_assert):
    """Tests access to VM attributes using /api/vms.

    Metadata:
        test_flag: rest
    """
    outcome = query_resource_attributes(vm)
    for failure in outcome.failed:
        if failure.type == 'attribute' and failure.name == 'policy_events' and BZ(
                1546995, forced_streams=['5.8', '5.9', 'upstream']).blocks:
            continue
        # this one is expected because additional arguments are needed
        if failure.type == 'subcollection' and failure.name == 'metric_rollups':
            continue
        soft_assert(False, '{0} "{1}": status: {2}, error: `{3}`'.format(
            failure.type, failure.name, failure.response.status_code, failure.error))


@pytest.mark.tier(3)
@pytest.mark.parametrize(
    'from_detail', [True, False],
    ids=['from_detail', 'from_collection'])
def test_edit_vm(request, vm, appliance, from_detail):
    """Tests edit VMs using REST API.

    Testing BZ 1428250.

    Metadata:
        test_flag: rest
    """
    request.addfinalizer(vm.action.delete)
    new_description = 'Test REST VM {}'.format(fauxfactory.gen_alphanumeric(5))
    payload = {'description': new_description}
    if from_detail:
        edited = vm.action.edit(**payload)
        assert_response(appliance)
    else:
        payload.update(vm._ref_repr())
        edited = appliance.rest_api.collections.vms.action.edit(payload)
        assert_response(appliance)
        edited = edited[0]

    record, __ = wait_for(
        lambda: appliance.rest_api.collections.vms.find_by(
            description=new_description) or False,
        num_sec=100,
        delay=5,
    )
    vm.reload()
    assert vm.description == edited.description == record[0].description


@pytest.mark.tier(3)
@pytest.mark.parametrize('method', ['post', 'delete'], ids=['POST', 'DELETE'])
def test_delete_vm_from_detail(vm, appliance, method):
    del_action = getattr(vm.action.delete, method.upper())
    del_action()
    assert_response(appliance)
    vm.wait_not_exists(num_sec=300, delay=10)
    with error.expected('ActiveRecord::RecordNotFound'):
        del_action()
    assert_response(appliance, http_status=404)


@pytest.mark.tier(3)
def test_delete_vm_from_collection(vm, appliance):
    collection = appliance.rest_api.collections.vms
    delete_resources_from_collection(collection, [vm], not_found=True, num_sec=300, delay=10)
