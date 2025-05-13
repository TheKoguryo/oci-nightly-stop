import inspect
import oci

from modules.oci_service import OciService

class DataIntegration(OciService):
    def __init__(self):
        self.SERVICE_NAME = 'Data Integration'


    def _get_resources(self, config, signer, compartment_id):
        client = oci.data_integration.DataIntegrationClient(config=config, signer=signer)

        resources = oci.pagination.list_call_get_all_results(
            client.list_workspaces,
            compartment_id
        )

        return resources.data


    def _perform_resource_action(self, config, signer, resource_id, action):
        client = oci.data_integration.DataIntegrationClient(config=config, signer=signer)
    
        if (action == 'STOP'):
            stop_response = client.stop_workspace(
                resource_id
            )
    
            response = client.get_workspace(
                resource_id
            )  
    
        return response.data, stop_response.headers['Date']      
 