import inspect
import oci

from modules.oci_service import OciService

class MySQL(OciService):
    def __init__(self):
        self.SERVICE_NAME = 'MySQL'


    def _get_resources(self, config, signer, compartment_id):
        client = oci.mysql.DbSystemClient(config=config, signer=signer)

        resources = oci.pagination.list_call_get_all_results(
            client.list_db_systems,
            compartment_id
        )

        return resources.data 


    def _perform_resource_action(self, config, signer, resource_id, action):
        client = oci.mysql.DbSystemClient(config=config, signer=signer)
    
        details = oci.mysql.models.StopDbSystemDetails(shutdown_type="FAST")
    
        if (action == 'STOP'):  
            stop_response = client.stop_db_system(
                resource_id,
                details
            )
    
            response = client.get_db_system(
                resource_id
            )        
    
        return response.data, stop_response.headers['Date']

