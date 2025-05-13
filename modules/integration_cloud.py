import inspect
import oci

from modules.oci_service import OciService

class IntegrationCloud(OciService):
    def __init__(self):
        self.SERVICE_NAME = 'Integration Cloud'


    def _get_resources(self, config, signer, compartment_id):
        resources = []
    
        client = oci.integration.IntegrationInstanceClient(config=config, signer=signer)
        summary = oci.pagination.list_call_get_all_results(
            client.list_integration_instances,
            compartment_id
        )
    
        for inst in summary.data:
            resource = client.get_integration_instance(inst.id)
    
            resources.append(resource.data)
    
        return resources    


    def _perform_resource_action(self, config, signer, resource_id, action):
        client = oci.integration.IntegrationInstanceClient(config=config, signer=signer)
    
        if (action == 'STOP'):      
            stop_response = client.stop_integration_instance(
                resource_id
            )
    
            response = client.get_integration_instance(
                resource_id
            )
    
        return response.data, stop_response.headers['Date']


    def _change_license_model(self, config, signer, resource_id, resource, license_type):
        is_byol = True if license_type == 'BRING_YOUR_OWN_LICENSE' else False

        client = oci.integration.IntegrationInstanceClient(config=config, signer=signer)
        details = oci.integration.models.UpdateIntegrationInstanceDetails(is_byol = is_byol)
    
        response = client.get_integration_instance(
            resource_id
        )
    
        if response.data.lifecycle_state == 'INACTIVE':
            return response.data, None
        
        update_response = client.update_integration_instance(
            resource_id,
            details
        )
    
        response = client.get_integration_instance(
            resource_id
        )
        
        oci.wait_until(
            client, 
            response, 
            evaluate_response=lambda r: r.data.lifecycle_state == 'ACTIVE'
        )

        response = client.get_integration_instance(
            resource_id
        )        
    
        return response.data, update_response.headers['Date']