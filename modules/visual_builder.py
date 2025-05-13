import inspect
import oci

from modules.oci_service import OciService

class VisualBuilder(OciService):
    def __init__(self):
        self.SERVICE_NAME = 'Visual Builder'


    def _get_resources(self, config, signer, compartment_id):
        resources = []
    
        client = oci.visual_builder.VbInstanceClient(config=config, signer=signer)
        summary = oci.pagination.list_call_get_all_results(
            client.list_vb_instances,
            compartment_id
        )
    
        for inst in summary.data:
            resource = client.get_vb_instance(vb_instance_id=inst.id)
    
            resources.append(resource.data)
    
        return resources


    def _perform_resource_action(self, config, signer, resource_id, action):
        client = oci.visual_builder.VbInstanceClient(config=config, signer=signer)
    
        if (action == 'STOP'):    
            stop_response = client.stop_vb_instance(
                resource_id
            )
    
            response = client.get_vb_instance(
                resource_id
            )
    
        return response.data, stop_response.headers['Date']
