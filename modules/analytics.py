import inspect
import oci

from modules.oci_service import OciService

class Analytics(OciService):
    def __init__(self):
        self.SERVICE_NAME = 'Analytics Cloud'


    def _get_resources(self, config, signer, compartment_id):
        resources = []
    
        client = oci.analytics.AnalyticsClient(config=config, signer=signer)
        summary = oci.pagination.list_call_get_all_results(
            client.list_analytics_instances,
            compartment_id
        )
    
        for inst in summary.data:
            resource = client.get_analytics_instance(analytics_instance_id=inst.id)
    
            resources.append(resource.data)
    
        return resources


    def _perform_resource_action(self, config, signer, resource_id, action):
        client = oci.analytics.AnalyticsClient(config=config, signer=signer)
    
        if (action == 'STOP'):
            stop_response = client.stop_analytics_instance(resource_id)
    
            response = client.get_analytics_instance(resource_id)
    
        return response.data, stop_response.headers['Date']        


    def _change_license_model(self, config, signer, resource_id, resource, license_type):
        client = oci.analytics.AnalyticsClient(config=config, signer=signer)
        details = oci.analytics.models.UpdateAnalyticsInstanceDetails(license_type = license_type)
        
        update_response = client.update_analytics_instance(
            resource_id,
            details
        )
    
        response = client.get_analytics_instance(
            resource_id
        )      
    
        oci.wait_until(
            client, 
            response, 
            evaluate_response=lambda r: r.data.lifecycle_state == 'ACTIVE'
        )
    
        response = client.get_analytics_instance(
            resource_id
        )    
    
        return response.data, update_response.headers['Date']     