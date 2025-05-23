import inspect
import oci

from modules.oci_service import OciService

class GoldenGate(OciService):
    def __init__(self):
        self.SERVICE_NAME = 'Golden Gate'


    def _get_resources(self, config, signer, compartment_id):
        client = oci.golden_gate.GoldenGateClient(config=config, signer=signer)

        resources = oci.pagination.list_call_get_all_results(
            client.list_deployments,
            compartment_id
        )

        return resources.data


    def _perform_resource_action(self, config, signer, resource_id, action):
        client = oci.golden_gate.GoldenGateClient(config=config, signer=signer)
        details = oci.golden_gate.models.StopDeploymentDetails(type="DEFAULT")
    
        if (action == 'STOP'):
            stop_response = client.stop_deployment(
                resource_id,
                details
            )
    
            response = client.get_deployment(
                resource_id
            )        
    
        return response.data, stop_response.headers['Date']


    def _change_license_model(self, config, signer, resource_id, resource, license_model):
        client = oci.golden_gate.GoldenGateClient(config=config, signer=signer)
        details = oci.golden_gate.models.UpdateDeploymentDetails(license_model = license_model)
        
        update_response = client.update_deployment(
            resource_id,
            details
        )
    
        response = oci.wait_until(
            client, 
            client.get_deployment(resource_id), 
            evaluate_response=lambda r: r.data.lifecycle_state in ['ACTIVE', 'INACTIVE']
        ) 

        return response.data, update_response.headers['Date']