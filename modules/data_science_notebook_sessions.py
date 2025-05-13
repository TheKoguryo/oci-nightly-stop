import inspect
import oci

from modules.oci_service import OciService

class DataScienceNotebookSession(OciService):
    def __init__(self):
        self.SERVICE_NAME = 'Data Science - Notebook Session'


    def _get_resources(self, config, signer, compartment_id):
        client = oci.data_science.DataScienceClient(config=config, signer=signer)

        resources = oci.pagination.list_call_get_all_results(
            client.list_notebook_sessions,
            compartment_id
        )

        return resources.data


    def _perform_resource_action(self, config, signer, resource_id, action):
        client = oci.data_science.DataScienceClient(config=config, signer=signer)
    
        if (action == 'STOP'):
            stop_response = client.deactivate_notebook_session(
                resource_id
            )
    
            response = client.get_notebook_session(
                resource_id
            )  
    
        return response.data, stop_response.headers['Date']
 