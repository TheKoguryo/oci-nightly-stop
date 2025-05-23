import inspect
import oci
import logging

from modules.oci_service import OciService

class AutonomousDatabase(OciService):
    def __init__(self):
        self.SERVICE_NAME = 'Autonomous Database'


    def _get_resources(self, config, signer, compartment_id):
        client = oci.database.DatabaseClient(config=config, signer=signer)
    
        resources = oci.pagination.list_call_get_all_results(
            client.list_autonomous_databases,
            compartment_id=compartment_id
        )
     
        return resources.data        


    def _perform_resource_action(self, config, signer, resource_id, action):
        client = oci.database.DatabaseClient(config=config, signer=signer)

        response = client.stop_autonomous_database(
            resource_id
        )

        return response.data, response.headers['Date']             


    def _change_license_model(self, config, signer, resource_id, resource, license_model):
        client = oci.database.DatabaseClient(config=config, signer=signer)
        details = oci.database.models.UpdateAutonomousDatabaseDetails(license_model = license_model)
    
        if license_model == 'BRING_YOUR_OWN_LICENSE':
            details = oci.database.models.UpdateAutonomousDatabaseDetails(license_model = license_model, database_edition='ENTERPRISE_EDITION')
        
        update_response = client.update_autonomous_database(
            resource_id,
            details
        )
    
        response = oci.wait_until(
            client, 
            client.get_autonomous_database(resource_id), 
            evaluate_response=lambda r: r.data.lifecycle_state in ['AVAILABLE', 'STOPPED']
        )   
    
        return response.data, update_response.headers['Date']


    def _get_name(self, resource):
        if hasattr(resource, 'display_name'):
            return resource.display_name

        return resource.name
    
    
    def _can_change_license(self, resource):
        if resource.db_workload != 'OLTP' and resource.db_workload != 'DW':
            return False, ":" + resource.db_workload
        
        if hasattr(resource, 'is_dev_tier') and (resource.is_dev_tier == True):
            return False, ":developer"
        
        if hasattr(resource, 'is_free_tier') and (resource.is_free_tier == True):
            return False, ":always_free"

        return True, ""