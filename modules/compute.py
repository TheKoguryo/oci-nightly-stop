import inspect
import oci

from modules.oci_service import OciService

class Compute(OciService):
    def __init__(self):
        self.SERVICE_NAME = 'Compute'


    def _get_resources(self, config, signer, compartment_id):
        client = oci.core.ComputeClient(config=config, signer=signer)

        resources = oci.pagination.list_call_get_all_results(
            client.list_instances,
            compartment_id
        )

        return resources.data


    def _perform_resource_action(self, config, signer, resource_id, action):
        client = oci.core.ComputeClient(config=config, signer=signer)

        response = client.instance_action(resource_id, action)
    
        return response.data, response.headers['Date']        