import inspect
import logging
import oci

from modules.oci_service import OciService

class BaseDatabase(OciService):
    def __init__(self):
        self.SERVICE_NAME = 'Oracle Base Database'


    def _get_resources(self, config, signer, compartment_id):
        resources = []

        db_systems = self._get_db_system_list(config, signer, compartment_id)

        caller_name = inspect.stack()[1].function
        if caller_name == "change_license_to_byol":
            return db_systems

        for db_system in db_systems:
            logging.info("      {} ({})".format(db_system.display_name, db_system.lifecycle_state))

            db_nodes = self._get_db_node_list(config, signer, compartment_id, db_system.id)

            for db_node in db_nodes:

                if (db_node.lifecycle_state == 'AVAILABLE'):
                    logging.info("        - node:{} ({})".format(db_node.hostname, db_node.lifecycle_state))
                    #db_node.compartment_name = compartment.name
                    db_node.display_name = db_system.display_name + " - Node: " + db_node.hostname
                    db_node.region = config["region"]
                    db_node.defined_tags = db_system.defined_tags
                    db_node.license_model = db_system.license_model
                    #db_node.service_name = SERVICE_NAME
                    resources.append(db_node)
                else:
                    logging.info("          node:{} ({})".format(db_node.hostname, db_node.lifecycle_state))

        return resources


    def _perform_resource_action(self, config, signer, resource_id, action):
        client = oci.database.DatabaseClient(config=config, signer=signer)

        response = client.db_node_action(
            resource_id,
            action
        )
    
        return response.data, response.headers['Date']                  


    def _change_license_model(self, config, signer, resource_id, resource, license_model):
        client = oci.database.DatabaseClient(config=config, signer=signer)
        details = oci.database.models.UpdateDbSystemDetails(license_model = license_model)
        
        update_response = client.update_db_system(
            resource_id,
            details
        )

        response = oci.wait_until(
            client, 
            client.get_db_system(resource_id), 
            evaluate_response=lambda r: r.data.lifecycle_state in ['AVAILABLE', 'STOPPED']
        ) 

        return response.data, update_response.headers['Date']


    def _get_db_system_list(self, config, signer, compartment_id):
        client = oci.database.DatabaseClient(config=config, signer=signer)
        resources = oci.pagination.list_call_get_all_results(
            client.list_db_systems,
            compartment_id=compartment_id
        )
        return resources.data
    
    
    def _get_db_node_list(self, config, signer, compartment_id, db_system_id):
        client = oci.database.DatabaseClient(config=config, signer=signer)
        resources = oci.pagination.list_call_get_all_results(
            client.list_db_nodes,
            compartment_id = compartment_id,
            db_system_id = db_system_id
        )
        return resources.data