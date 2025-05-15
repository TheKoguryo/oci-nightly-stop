# coding: utf-8
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

import oci
from datetime import timedelta
from datetime import datetime
import argparse
import pytz
from oci.signer import Signer
import configuration
from modules.utils import *
from modules.oci_service import OciService
from modules.compute import Compute
from modules.analytics import Analytics
from modules.autonomous_database import AutonomousDatabase
from modules.base_database import BaseDatabase
from modules.data_integration import DataIntegration
from modules.data_science_model_deployements import DataScienceModelDeployment
from modules.data_science_notebook_sessions import DataScienceNotebookSession
from modules.digital_assistant import DigitalAssistant
from modules.goldengate import GoldenGate
from modules.integration_cloud import IntegrationCloud
from modules.mysql import MySQL
from modules.visual_builder import VisualBuilder


class Compartment:
    def __init__(self, id, name, timezone):
        self.id = id 
        self.name = name    
        self.timezone = timezone    

    def __str__(self):
        return f"id: {self.id}, name: {self.name}, timezone: {self.timezone}"

    def __eq__(self, other):
        return (self.id == other.id) and (self.name == other.name) and (self.timezone == other.timezone)


##########################################################################
# set parser
##########################################################################
def parse_csv(value):
    return [v.strip() for v in value.split(',') if v.strip()]


def set_parser_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument('--regions', nargs="*", default="", dest='regions', help='List target regions. All regions will be counted if null')
    parser.add_argument('--excl_regions', nargs="*", default="", dest='excl_regions', help='List excluded regions.')
    parser.add_argument('--filter-tz', type=parse_csv, dest='filter_tz', help='Comma-separated list of timezones to include or exclude')
    parser.add_argument('--filter-mode', choices=['include', 'exclude'], dest='filter_mode', help='Filtering mode: include = only these timezones, exclude = all but these')

    result = parser.parse_args()
   
    return result 


##########################################################################
# Main
##########################################################################
if __name__ == "__main__":
    args = set_parser_arguments()
    if args is None:
        exit()

    target_region_names = args.regions if args.regions else []
    excluded_region_names = args.excl_regions if args.excl_regions else []
    filter_tz = args.filter_tz if args.filter_tz else []
    filter_mode = args.filter_mode if args.filter_mode else "include"

    logging.info("target_region_names: %r" % target_region_names)
    logging.info("excluded_region_names: %r" % excluded_region_names)
    logging.info("filter_tz: %r" % filter_tz)
    logging.info("filter_mode: %r" % filter_mode)
    
    config = None
    tenancy_id = None
    
    if configuration.use_instance_principal.upper() == 'TRUE':
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        config = {'region': signer.region, 'tenancy': signer.tenancy_id, 'user': 'instance_principal'}
        tenancy_id = signer.tenancy_id
        
        tenancy_name=get_tenancy_name(config, signer, signer.tenancy_id)
        signer.tenancy_name = tenancy_name
    else:
        config = oci.config.from_file(configuration.configfile, configuration.profile)
    
        signer = Signer(
            tenancy = config['tenancy'],
            user = config['user'],
            fingerprint = config['fingerprint'],
            private_key_file_location = config['key_file'],
            pass_phrase = config['pass_phrase']
        )
    
        tenancy_id = config['tenancy']    
        tenancy_name=get_tenancy_name(config, signer, signer.tenancy_id)
        signer.tenancy_name = tenancy_name
    
        logging.info("=========================== [ Login check ] =============================")
        login(config, signer)

    logging.info("========================== [ Target regions ] ===========================")
    all_regions = get_region_subscription_list(config, signer, tenancy_id)
    target_regions=[]
    target_regions_by_name=dict()
    for region in all_regions:
        if ((not configuration.target_region_names) or (region.region_name in configuration.target_region_names)) and (region.region_name not in configuration.excluded_region_names):
            target_regions.append(region)
            target_regions_by_name[region.region_name]=region
            logging.debug(region)
            logging.info(region.region_name)

    logging.info("======================== [ Target compartments ] ========================")
    if not configuration.top_level_compartment_id:
        configuration.top_level_compartment_id = tenancy_id
    compartments = get_compartment_list(config, signer, configuration.top_level_compartment_id, configuration.excluded_parent_compartments)
    target_compartments=[]
    target_compartments_by_id=dict()
    for compartment in compartments:
        if compartment.name not in configuration.excluded_compartments:
            target_compartments.append(compartment)
            target_compartments_by_id[compartment.id]=compartment
            logging.info(compartment.name)


    logging.info("============== [ Usage Based Target regions & compartments ] ==============")
    usage_api_client = oci.usage_api.UsageapiClient(config=config, signer=signer)

    timezone = pytz.timezone('UTC')
    today = datetime.now(timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    d_day_started = today - timedelta(days=14)

    usages = usage_api_client.request_summarized_usages(
                request_summarized_usages_details=oci.usage_api.models.RequestSummarizedUsagesDetails(
                    tenant_id=tenancy_id,
                    time_usage_started=d_day_started,
                    time_usage_ended=today,
                    granularity="MONTHLY",
                    group_by=["region", "service", "compartmentName", "compartmentId"],
                    compartment_depth=6
                )
            ).data

    target = dict()
    identity_client = oci.identity.IdentityClient(config, signer=signer)
    for item in usages.items:

        if item.region not in target_regions_by_name:
            continue

        if item.compartment_id not in target_compartments_by_id:
            continue
    
        if item.computed_amount is None or item.computed_amount == 0.0:
            continue

        compartment_timezone = target_compartments_by_id[item.compartment_id].defined_tags.get('Control', {}).get('Timezone', '')

        compartment = Compartment(item.compartment_id, item.compartment_name, str(compartment_timezone))

        isNew = False
        if item.region in target:
            if item.service in target[item.region]:
                if compartment not in target[item.region][item.service]:
                    target[item.region][item.service].append(compartment)
                    isNew = True
            else:
                target[item.region][item.service]=[]
                target[item.region][item.service].append(compartment)    
                isNew = True        
        else:
            target[item.region] = dict()
            target[item.region][item.service] = []
            target[item.region][item.service].append(compartment)
            isNew = True
    
        if isNew:
            logging.info("region: {:20s} compartment_name: {:30s} service: {}".format(item.region, item.compartment_name, item.service))

    logging.info("IS_FIRST_FRIDAY: " + str(IS_FIRST_FRIDAY))
    if IS_FIRST_FRIDAY:
        logging.info("=============== [ Today is First Friday of This Month ] ===============")
        logging.info("Stop the World")

    processed_resources = []
    for region in target:
        logging.info("")
        logging.info("============ [ {} ] ================".format(region))
    
        config["region"] = region

        if "Analytics" in target[region]:
            service_name = "Analytics"
            logging.info("### {}".format(service_name))
            target_compartments = target[region][service_name]

            client = Analytics()

            if configuration.is_internal_tenancy == 'TRUE':
                client.change_license_to_byol(config, signer, target_compartments, filter_tz, filter_mode)  

            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode)  
            processed_resources += resources        


        if "Database" in target[region]:
            service_name = "Database"
            logging.info("### {}".format(service_name))
            target_compartments = target[region][service_name]

            client = AutonomousDatabase()

            if configuration.is_internal_tenancy == 'TRUE':
                client.change_license_to_byol(config, signer, target_compartments, filter_tz, filter_mode)  

            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode)
            processed_resources += resources

            client = BaseDatabase()

            if configuration.is_internal_tenancy == 'TRUE':
                client.change_license_to_byol(config, signer, target_compartments, filter_tz, filter_mode)  

            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode)
            processed_resources += resources  


        if "Compute" in target[region]:
            service_name = "Compute"
            logging.info("### {}".format(service_name))
            target_compartments = target[region][service_name]

            client = Compute()
            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode)
            processed_resources += resources


        if "Data Integration" in target[region]:
            service_name = "Data Integration"
            logging.info("### {}".format(service_name))
            target_compartments = target[region][service_name]
        
            client = DataIntegration() 

            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode) 
            processed_resources += resources     


        if "Data Science" in target[region]:
            service_name = "Data Science"
            logging.info("### {}".format(service_name))
            target_compartments = target[region][service_name]

            client = DataScienceModelDeployment() 

            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode) 
            processed_resources += resources 

            client = DataScienceNotebookSession() 

            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode)  
            processed_resources += resources                                             


        if "Digital Assistant" in target[region]:
            service_name = "Digital Assistant"
            logging.info("### {}".format(service_name))
            target_compartments = target[region][service_name]

            client = DigitalAssistant() 

            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode)   
            processed_resources += resources           


        if "GoldenGate" in target[region]:
            service_name = "GoldenGate"
            logging.info("### {}".format(service_name))
            target_compartments = target[region][service_name]

            client = GoldenGate() 

            if configuration.is_internal_tenancy == 'TRUE':
                client.change_license_to_byol(config, signer, target_compartments, filter_tz, filter_mode)             

            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode) 
            processed_resources += resources             


        if "Integration Service" in target[region]:
            service_name = "Integration Service"
            logging.info("### {}".format(service_name))
            target_compartments = target[region][service_name]

            client = IntegrationCloud() 

            if configuration.is_internal_tenancy == 'TRUE':
                client.change_license_to_byol(config, signer, target_compartments, filter_tz, filter_mode)             

            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode)   
            processed_resources += resources   


        if "MySQL" in target[region]:
            service_name = "MySQL"
            logging.info("### {}".format(service_name))
            target_compartments = target[region][service_name]

            client = MySQL()          

            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode)  
            processed_resources += resources


        if "Visual Builder" in target[region]:
            service_name = "Visual Builder"
            logging.info("### {}".format(service_name))
            target_compartments = target[region][service_name]

            client = VisualBuilder()          

            resources = client.stop_resources(config, signer, target_compartments, filter_tz, filter_mode)  
            processed_resources += resources

    logging.info("")
    revised_target_resources = dict()
    for resource in processed_resources:
        if hasattr(resource, 'display_name'):
            logging.info("{} in {}".format(resource.display_name, resource.compartment_name))
        else:
            logging.info("{} in {}".format(resource.name, resource.compartment_name))     

        logging.info("  resource_id: " + resource.id)
        created_by = get_created_by(config, signer, resource)
        logging.info("    created_by: " + created_by)

        owner_email = None
        identity_domain_name = None
        user_name = None
    
        if created_by is not None:
            if '/' in created_by:
                identity_domain_name = created_by.rsplit('/', 1)[0]
                user_name = created_by.rsplit('/', 1)[1]                
            else:
                identity_domain_name = "default"
                user_name = created_by   

            if is_email_format(user_name) == True:
                owner_email = user_name
            else:
                owner_email = get_user_email(config, signer, identity_domain_name, user_name)

            logging.info("      owner_email: " + owner_email)                

            if owner_email in revised_target_resources:
                revised_target_resources[owner_email].append(resource)
            else:
                revised_target_resources[owner_email] = []
                revised_target_resources[owner_email].append(resource)

    logging.info("")
    for created_by in revised_target_resources:
        logging.info("created_by: " + created_by)
        region = ""
        for resource in revised_target_resources[created_by]:
            if region != resource.region:
                logging.info("  " + resource.region)
                region = resource.region
            
            if hasattr(resource, 'display_name'):
                logging.info("    {} | {} in {}".format(resource.service_name, resource.display_name, resource.compartment_name))
            else:
                logging.info("    {} | {} in {}".format(resource.service_name, resource.name, resource.compartment_name))

        try:
            send_nightly_stop_notification(config, signer, created_by, revised_target_resources[created_by])
        except Exception as ex:
            logging.error("ERROR: ", ex)