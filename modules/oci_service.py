import oci
import socket
import inspect

from modules.utils import *

class OciService:
    def __init__(self):
        self.SERVICE_NAME = 'NONE'
    

    def stop_resources(self, config, signer, compartments, filter_tz, filter_mode):
        target_resources = []
        processed_resources = []
    
        logging.info("Listing all {} resources... (* is marked for stop)".format(self.SERVICE_NAME))
        for compartment in compartments:
            logging.info("  compartment: {}, timezone: {}".format(compartment.name, compartment.timezone))
    
            if filter_mode == "include":
                if compartment.timezone not in filter_tz:
                    logging.info("      (skipped) Target timezones: {}".format(filter_tz))
                    continue
            else:
                if compartment.timezone in filter_tz:
                    logging.info("      (skipped) Target timezones: all timezone excluding {}".format(filter_tz))
                    continue
    
            resources = self._get_resources(config, signer, compartment.id)
            for resource in resources:
                action_required = False
                nightly_stop_tag = resource.defined_tags.get('Control', {}).get('Nightly-Stop', '').upper()
                if resource.lifecycle_state == 'DELETED':
                    continue

                if resource.lifecycle_state == 'RUNNING' or resource.lifecycle_state == 'ACTIVE' or resource.lifecycle_state == 'AVAILABLE':
                    if IS_FIRST_FRIDAY:
                        action_required = True
                    
                    if nightly_stop_tag != 'FALSE':   
                        action_required = True
    
                    # Don't stop the VM that run this nightly-stop.
                    if self._get_name(resource) == socket.gethostname():
                        action_required = False  

                    if resource.id in configuration.excluded_resource_ids:
                        action_required = False                      

                    if "-instance-pool-" in str(self._get_name(resource)): 
                        action_required = False

                if action_required:
                    logging.info("    * {} ({}) in {}".format(self._get_name(resource), resource.lifecycle_state, compartment.name))

                    resource.compartment_name = compartment.name
                    resource.service_name = self.SERVICE_NAME
                    resource.region = config["region"]
                    if resource.region == "iad":
                        resource.region = "us-ashburn-1"
                    elif resource.region == "phx":
                        resource.region = "us-phoenix-1"                    
                    target_resources.append(resource)
                else:
                    if nightly_stop_tag != '':      
                        logging.info("      {} ({}) in {} - {}:{}".format(self._get_name(resource), resource.lifecycle_state, compartment.name, 'Control.Nightly-Stop', nightly_stop_tag))
                    else:
                        logging.info("      {} ({}) in {}".format(self._get_name(resource), resource.lifecycle_state, compartment.name))

        if len(target_resources) > 0:
            logging.info("")
            logging.info('Stopping * marked {} resources...'.format(self.SERVICE_NAME))
        for resource in target_resources:
            try:
                response, request_date = self._perform_resource_action(config, signer, resource.id, 'STOP')
                processed_resources.append(resource)
            except oci.exceptions.ServiceError as e:              
                logging.error(f"Error stopping resource {self._get_name(resource)}: {e}")             
            else:
                logging.info("    stop requested: {} ({}) in {}".format(self._get_name(resource), response.lifecycle_state, resource.compartment_name))

        if len(processed_resources) > 0:
            logging.info("    {} resources stopped!".format(len(processed_resources)))
    
        return processed_resources


    def change_license_to_byol(self, config, signer, compartments, filter_tz, filter_mode):
        target_resources = []
        processed_resources = []
    
        logging.info("Listing all {} resources... (* is marked for license change)".format(self.SERVICE_NAME))
        for compartment in compartments:
            logging.info("  compartment: {}, timezone: {}".format(compartment.name, compartment.timezone))
    
            if filter_mode == "include":
                if compartment.timezone not in filter_tz:
                    logging.info("      (skipped) Target timezones: {}".format(filter_tz))
                    continue
            else:
                if compartment.timezone in filter_tz:
                    logging.info("      (skipped) Target timezones: all timezone excluding {}".format(filter_tz))
                    continue
    
            resources = self._get_resources(config, signer, compartment.id)
            for resource in resources:
                action_required = False
                message = ""
                byol_tag = resource.defined_tags.get('Control', {}).get('BYOL', '').upper()
                if (self._get_license(resource) == 'LICENSE_INCLUDED') and byol_tag != 'FALSE':
                    action_required, message = self._can_change_license(resource)                                       
                            
                if action_required:             
                    logging.info("    * {} ({}) in {}".format(self._get_name(resource), self._get_license(resource), compartment.name))

                    resource.compartment_name = compartment.name
                    resource.service_name = self.SERVICE_NAME
                    resource.region = config["region"] 
                    target_resources.append(resource)
                else:                         
                    if byol_tag != '':       
                        logging.info("      {} ({}{}) in {} - {}:{}".format(self._get_name(resource), self._get_license(resource), message, compartment.name, 'Control.BYOL', byol_tag))
                    else:
                        logging.info("      {} ({}{}) in {}".format(self._get_name(resource), self._get_license(resource), message, compartment.name))                        

        if len(target_resources) > 0:
            logging.info("")
            logging.info("Changing * marked {}'s license model...".format(self.SERVICE_NAME))
        for resource in target_resources:
            name = resource.display_name if hasattr(resource, 'display_name') else resource.name

            try:
                response, request_date = self._change_license_model(config, signer, resource.id, resource, 'BRING_YOUR_OWN_LICENSE')
                if response != None:
                    processed_resources.append(resource)
            except oci.exceptions.ServiceError as e:
                logging.error(f"Error Changing resource {self._get_name(resource)}: {e}")                
            else:
                if response != None:
                    send_license_type_change_notification(config, signer, self.SERVICE_NAME, resource, request_date, 'BYOL')
                    logging.info("    changed to: {} ({})".format(self._get_name(resource), self._get_license(response)))

        if len(processed_resources) > 0:
            logging.info("{} resources are changed!".format(len(processed_resources)))
    
        return processed_resources


    def _get_resources(self, config, signer, compartment_id):
        # Implement the logic to retrieve resources here
        pass


    def _perform_resource_action(self, config, signer, resource_id, action):
        # Implement the logic to perform the action here (e.g., stopping a resource)
        pass


    def _change_license_model(self, config, signer, resource_id, resource, license_type):
        pass


    def _get_name(self, resource):
        if hasattr(resource, 'display_name'):
            return resource.display_name

        return resource.name


    def _get_license(self, resource):
        if hasattr(resource, 'license_model'):
            return resource.license_model

        if hasattr(resource, 'is_byol') and resource.is_byol == False:
            return 'LICENSE_INCLUDED'
        else:
            return 'BRING_YOUR_OWN_LICENSE'          

        return resource.license_type


    def _can_change_license(self, resource):
        return True, ""