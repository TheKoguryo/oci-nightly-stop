import oci
import logging
import re
from datetime import datetime, timedelta

import smtplib
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import configuration


def login(config, signer):
    identity = oci.identity.IdentityClient(config, signer=signer)
    user = identity.get_user(config['user']).data
    logging.info("Logged in as: {} @ {}".format(user.description, config['region']))


def get_tenancy_name(config, signer, tenancy_id):
    identity = oci.identity.IdentityClient(config, signer=signer)

    tenancy_name = identity.get_tenancy(tenancy_id).data.name

    return tenancy_name 


def get_region_subscription_list(config, signer, tenancy_id):
    identity = oci.identity.IdentityClient(config, signer=signer)
    response = identity.list_region_subscriptions(
        tenancy_id
    )
    return response.data


def get_compartment_list(config, signer, compartment_id, excluded_parent_compartments):
    identity = oci.identity.IdentityClient(config, signer=signer)

    target_compartments = []
    all_compartments = []

    top_level_compartment_response = identity.get_compartment(compartment_id)
    target_compartments.append(top_level_compartment_response.data)
    all_compartments.append(top_level_compartment_response.data)

    while len(target_compartments) > 0:
        target = target_compartments.pop(0)

        if target.name in excluded_parent_compartments:
            continue

        child_compartment_response = oci.pagination.list_call_get_all_results(
            identity.list_compartments,
            compartment_id=target.id,
            lifecycle_state="ACTIVE"
        )
        target_compartments.extend(child_compartment_response.data)
        all_compartments.extend(child_compartment_response.data)

    return all_compartments
    

def is_email_format(value):
    obj = re.search(r'[\w.]+\@[\w.]+', value)
    if not obj:
        return False

    return True


def get_created_by(config, signer, resource):
    created_by = None
    
    identity_domain_name = None
    user_name = None

    logging.info("    resource_id: " + resource.id)

    if hasattr(resource, 'created_by'):
        created_by = resource.created_by
        logging.info("    created_by: " + created_by)

        if created_by.startswith('ocid1.'):
            if (created_by.startswith("ocid1.datasciencenotebooksession")):
                notebook_session_id = created_by
    
                try:
                    client = oci.data_science.DataScienceClient(config=config, signer=signer)
                    get_notebook_session_response = client.get_notebook_session(notebook_session_id)

                    created_by = get_created_by(config, signer, get_notebook_session_response.data)
                except oci.exceptions.ServiceError as ex:
                    if ex.status == 404:
                        pass
                    else:
                        logging.error("ERROR: ", ex, flush=True)

            if created_by.startswith('ocid1.user.'):    
                identity_domain_name, user_name = get_user_by_user_id(config, signer, created_by)
                return identity_domain_name + "/" + user_name
            elif created_by.startswith('ocid1.saml2idp.'):
                user_name = created_by.rsplit('/', 1)[1]
                return user_name  
            else:
                return created_by                         

    if ('Oracle-Tags' in resource.defined_tags) and ('CreatedBy' in resource.defined_tags['Oracle-Tags']):  
        oracle_tags_created_by = str(resource.defined_tags['Oracle-Tags']['CreatedBy'])
        logging.info("    Oracle-Tags.CreatedBy: " + oracle_tags_created_by)     

        if oracle_tags_created_by.startswith('ocid1.nodepool.'):
            node_pool_id = oracle_tags_created_by
            logging.info("node_pool_id: " + str(node_pool_id))

            config["region"] = resource.region
            container_engine_client = oci.container_engine.ContainerEngineClient(config=config, signer=signer)

            try:
                get_node_pool_response = container_engine_client.get_node_pool(node_pool_id=node_pool_id)
                created_by = get_created_by(config, signer, get_node_pool_response.data)
            except oci.exceptions.ServiceError as ex:
                logging.error("ERROR: ", ex, flush=True)
                pass
        elif oracle_tags_created_by == 'oke':
            oke_cluster_id = resource.metadata['oke-cluster-id']

            config["region"] = resource.region
            container_engine_client = oci.container_engine.ContainerEngineClient(config=config, signer=signer)
            
            try:
                get_cluster_response = container_engine_client.get_cluster(cluster_id=oke_cluster_id)
                created_by = get_created_by(config, signer, get_cluster_response.data)
            except oci.exceptions.ServiceError as ex:
                logging.error("ERROR: ", ex, flush=True)
                pass
        elif oracle_tags_created_by.startswith('ocid1.desktoppool.'):
            desktoppool_id = oracle_tags_created_by

            config["region"] = resource.region
            desktops_client = oci.desktops.DesktopServiceClient(config, signer=signer)
            
            try:
                get_desktop_pool_response = desktops_client.get_desktop_pool(desktop_pool_id=desktoppool_id)
                created_by = get_created_by(config, signer, get_desktop_pool_response.data)
            except oci.exceptions.ServiceError as ex:
                logging.error("ERROR: ", ex, flush=True)
                pass            
        else:
            created_by = oracle_tags_created_by

    if created_by:           
        if '/' in created_by:
            identity_domain_name = created_by.rsplit('/', 1)[0]
            user_name = created_by.rsplit('/', 1)[1]
        else:
            identity_domain_name = 'default'
            user_name = created_by  

    if identity_domain_name:
        return identity_domain_name + "/" + user_name
    else:
        return user_name


def get_user_by_user_id(config, signer, user_id):
    user = None
    identity_domain_name = ""
    user_name = "" 

    identity_client = oci.identity.IdentityClient(config, signer=signer)   

    list_domains_response = identity_client.list_domains(
        compartment_id=signer.tenancy_id,
        #display_name=domain_display_name,
        lifecycle_state="ACTIVE")

    for identity_domains in list_domains_response.data:
        domain_endpoint = identity_domains.url;
        
        identity_domains_client = oci.identity_domains.IdentityDomainsClient(config, domain_endpoint, signer=signer)

        try:       
            user = identity_domains_client.get_user(user_id=user_id).data
            identity_domain_name = identity_domains.display_name.lower()
            user_name = user.user_name
            
            break;
        except oci.exceptions.ServiceError as ex:
            if ex.status == 404:
                continue
            logging.error("ERROR: ", ex, flush=True)
            continue

    #user_name = domain_display_name + "/" + user.display_name
    logging.info("    user_id: " + user_id)
    logging.info("    user_name: " + user_name)
    logging.info("    identity_domain_name: " + identity_domain_name)    

    return identity_domain_name, user_name


def get_user_email(config, signer, identity_domain_name, user_name):
    if user_name is None or user_name == "":
        return ""
    
    user_email = ""

    if identity_domain_name == "" or identity_domain_name is None:
        identity_domain_name = "default"

    identity_client = oci.identity.IdentityClient(config, signer=signer)   

    list_domains_response = identity_client.list_domains(
        compartment_id=signer.tenancy_id,
        display_name=identity_domain_name,
        lifecycle_state="ACTIVE")

    domain_endpoint = list_domains_response.data[0].url

    identity_domains_client = oci.identity_domains.IdentityDomainsClient(config, domain_endpoint, signer=signer)

    list_users_response = identity_domains_client.list_users(
        filter="userName eq \"" + user_name + "\"")        

    if len(list_users_response.data.resources) > 0:
        user = list_users_response.data.resources[0]

        for email in user.emails:
            if email.primary == True:
                user_email = email.value
                break

    return user_email


def send_license_type_change_notification(config, signer, service_name, resource, request_date_string, type):
    if configuration.enable_email_notification.upper() != 'TRUE':
        return
    
    if (type != 'BYOL'):
        return

    title = None
    resource_name = None
    to = None

    if hasattr(resource, 'name'):
        resource_name = resource.name
    else:
        resource_name = resource.display_name

    if ('Oracle-Tags' in resource.defined_tags) and ('CreatedBy' in resource.defined_tags['Oracle-Tags']):  
        created_by = str(resource.defined_tags['Oracle-Tags']['CreatedBy'])
        logging.info("created_by: " + created_by)   

        if created_by != "":
            created_by = created_by.replace("oracleidentitycloudservice/", "")
            created_by = created_by.replace("default/", "")

        #created_by = created_by.rsplit('/', 1)[1]    

        logging.info("created_by: " + created_by)

        if is_email_format(created_by) == True:
            to = created_by

    if to is None:
        to = configuration.bcc
    
    #KST = pytz.timezone('Asia/Seoul')
    #date_string = request_date_string
    #datetime_object = datetime.strptime(date_string, '%a, %d %b %Y %H:%M:%S %Z')
    #request_date_string = str(datetime_object.astimezone(KST))

    if configuration.language == "Korean":
        if (type == 'BYOL'):
            warningMessage = service_name + " Internal Tenancy 절약 모드"
            title = "[" + signer.tenancy_name + "] " + resource_name + " 라이센스 정책 변경 - BYOL"        
            main_message = signer.tenancy_name + " 테넌시 관리자가 설정한 Nightly Stop 자원 관리 정책에 따라, 스케줄러에 의해 아래 자원은 BYOL 라이센스로 변경되었습니다. <br>기존 라이센스 정책 사용을 원하는 경우, 해당 자원 태그에 Control.BYOL=FALSE로 설정 후, 원하는 라이센스로 변경하여 하여 사용하시기 바랍니다."
        else:
            warningMessage = "Nightly Stop - " + service_name + " 서비스 심야 절약 모드"     
            title = "[" + signer.tenancy_name + "] " + resource_name + " 일시 중지"
            main_message = signer.tenancy_name + " 테넌시 관리자가 설정한 Nightly Stop 자원 관리 정책에 따라, 스케줄러에 의해 아래 자원은 중지(Stop) 또는 비활성화(Deactivate) 되었습니다. <br>필요하신 시점에 시작(Start) 또는 활성화(Activate)하여 사용하시기 바랍니다."
        additionalMessage = "의문 사항이 있으면 클라우드 계정 관리자에게 문의하십시오."
        footerMessage = "이 메시지는 시스템에서 생성된 메시지입니다. 이 메시지 발신자에게 회신하지 마십시오."            
    else:
        if (type == 'BYOL'):
            warningMessage = service_name + " Internal Tenancy Cost Saving Mode"
            title = "[" + signer.tenancy_name + "] " + resource_name + " has been changed to BYOL licenses"        
            main_message = "In accordance with the Nightly Stop resource management policy configured by the " + signer.tenancy_name + " tenancy administrator, the following resource has been changed to BYOL licenses by the scheduler.<br> If you prefer to use the original license policy, please set the tag Control.BYOL=FALSE on the resource and then change it to your desired license."
        else:
            warningMessage = "Nightly Stop - " + service_name + " Late-Night Cost Saving Mode"     
            title = "[" + signer.tenancy_name + "] " + resource_name + " has been stopped"
            main_message = "As per the Nightly Stop resource management policy configured by the " + signer.tenancy_name + " tenancy administrator, the scheduler has stopped or deactivated the following resources. <br>You may start or activate them when needed."    

        additionalMessage = "If you have any questions, please contact your cloud account administrator."
        footerMessage = "This is a system-generated message. Please do not reply to the sender of this message."               

    if configuration.language == "Korean":
        template = Path('mail-template/license_type_change_notification_ko.html').read_text()
    else:
        template = Path('mail-template/license_type_change_notification_en.html').read_text()


    redirectUrl = "https://cloud.oracle.com"

    if resource.region == "iad":
        resource.region = "us-ashburn-1"
    elif resource.region == "phx":
        resource.region = "us-phoenix-1"

    if resource.id.startswith("ocid1.instance"):
        redirectUrl = "https://cloud.oracle.com/compute/instances/" + resource.id +"?region=" + resource.region
    elif resource.id.startswith("ocid1.dbnode"):
        redirectUrl = "https://cloud.oracle.com/dbaas/dbsystems/" + resource.db_system_id +"/nodes?region=" + resource.region
    elif resource.id.startswith("ocid1.dbsystem"):
        redirectUrl = "https://cloud.oracle.com/dbaas/dbsystems/" + resource.id +"/nodes?region=" + resource.region      
    elif resource.id.startswith("ocid1.autonomousdatabase"):
        redirectUrl = "https://cloud.oracle.com/db/adbs/" + resource.id +"?region=" + resource.region    
    elif resource.id.startswith("ocid1.odainstance"):
        redirectUrl = "https://cloud.oracle.com/digital-assistant/oda-instances/" + resource.id +"?region=" + resource.region
    elif resource.id.startswith("ocid1.analyticsinstance"):
        redirectUrl = "https://cloud.oracle.com/analytics/instances/" + resource.id +"?region=" + resource.region
    elif resource.id.startswith("ocid1.visualbuilderinstance"):
        redirectUrl = "https://cloud.oracle.com/vb/instances/" + resource.id +"?region=" + resource.region
    elif resource.id.startswith("ocid1.mysqldbsystem"):
        redirectUrl = "https://cloud.oracle.com/mysqlaas/db-systems/" + resource.id +"?region=" + resource.region
    elif resource.id.startswith("ocid1.integrationinstance"):
        redirectUrl = "https://cloud.oracle.com/oic/integration-instances/" + resource.id +"?region=" + resource.region
    elif resource.id.startswith("ocid1.datasciencenotebooksession"):
        redirectUrl = "https://cloud.oracle.com/data-science/notebook-sessions/" + resource.id +"?region=" + resource.region
    elif resource.id.startswith("ocid1.datasciencemodeldeployment"):
        redirectUrl = "https://cloud.oracle.com/data-science/model-deployments/" + resource.id +"?region=" + resource.region   
    elif resource.id.startswith("ocid1.disworkspace"):
        redirectUrl = "https://cloud.oracle.com/dis/" + resource.id +"/home?region=" + resource.region  
    elif resource.id.startswith("ocid1.goldengatedeployment"):
        redirectUrl = "https://cloud.oracle.com/goldengate/deployments/" + resource.id +"?region=" + resource.region  

    html_body = template.replace("${title}", title)
    html_body = html_body.replace("${companyName}", signer.tenancy_name)
    html_body = html_body.replace("${headerImage}", "https://ci3.googleusercontent.com/meips/ADKq_NbPxsLyenwFfmz-f6Je7pVsAipkskSYJASeBzieNgGFsW0GYaHme6TCvbb6LDKTtN1E227iYqEXEmxtk_mFau2muY15hrzfcKjujIjdDJEA6OprriPEMzNBy0HM2u_-UYnp7JtczGEDhcxa73WiwAlWk6JSNkWpOJC8wYwSoZk2A1UnjMN9q4tk7YIvbgFJ2oxjEEGQvDRY3-fIuQFteTqWqQI=s0-d-e1-ft#https://idcs-545bcf5ba488439e82f6294f0fc978bb.identity.oraclecloud.com:443/ui/v1/public/common/asset/defaultBranding/oracle-email-header.png")
    html_body = html_body.replace("${warningMessage}", warningMessage)
    html_body = html_body.replace("${mainMessage}", main_message)
    html_body = html_body.replace("${tenancyName}", signer.tenancy_name)
    html_body = html_body.replace("${region}", resource.region)
    html_body = html_body.replace("${compartmentName}", resource.compartment_name)
    html_body = html_body.replace("${serviceName}", service_name)
    html_body = html_body.replace("${resourceName}", resource_name)
    html_body = html_body.replace("${requestDate}", request_date_string)
    html_body = html_body.replace("${redirectUrl}", redirectUrl)
    html_body = html_body.replace("${additionalMessage}", additionalMessage)
    html_body = html_body.replace("${footerMessage}", footerMessage)

    send_email(configuration.sender_email, configuration.sender_name, to, configuration.cc, configuration.bcc, title, html_body)


def send_nightly_stop_notification(config, signer, created_by, target_resources):
    if configuration.enable_email_notification.upper() != 'TRUE':
        return

    title = None
    resource_name = None
    to = None
    
    domain_display_name = None
    user_name = None     

    if '/' in created_by:
        domain_display_name = created_by.rsplit('/', 1)[0]
        user_name = created_by.rsplit('/', 1)[1]
    else:
        domain_display_name = 'default'
        user_name = created_by    

    if is_email_format(user_name) == True:
        to = user_name
    else:
        email = get_user_email(config, signer, domain_display_name, user_name)
        logging.info("email: " + str(email))
        if email is not None and is_email_format(email) == True:
            to = email

    if to is None:
        to = configuration.bcc

    region = ""
    tbody = ""
    for resource in target_resources:
            
        if resource.region == "iad":
            resource.region = "us-ashburn-1"
        elif resource.region == "phx":
            resource.region = "us-phoenix-1"

        if region != resource.region:
            #logging.info("  " + resource.region)

            region = resource.region

            tbody += "\n  <!-- Region -->"
            tbody += "\n  <tr>"
            tbody += "\n      <td style=\"height:34px; font-family:'Malgun Gothic','Oracle Sans','Oracle Sans Regular',Helvetica,Arial,sans-serif; font-style:normal; font-weight:600; font-size:13.75px; color:#737371;\" valign='bottom'>" + region + "</td>"
            tbody += "\n  </tr>"
            tbody += "\n"      
            tbody += "\n  <!-- Separator-->"											
            tbody += "\n  <tr>"
            tbody += "\n      <td style='height:6px'></td>"
            tbody += "\n  </tr>"                  
        
        if hasattr(resource, 'name'):
            resource_name = resource.name
        else:
            resource_name = resource.display_name


        redirectUrl = "https://cloud.oracle.com"            

        if resource.id.startswith("ocid1.instance"):
            redirectUrl = "https://cloud.oracle.com/compute/instances/" + resource.id +"?region=" + resource.region
        elif resource.id.startswith("ocid1.dbnode"):
            redirectUrl = "https://cloud.oracle.com/dbaas/dbsystems/" + resource.db_system_id +"/nodes?region=" + resource.region
        elif resource.id.startswith("ocid1.dbsystem"):
            redirectUrl = "https://cloud.oracle.com/dbaas/dbsystems/" + resource.id +"/nodes?region=" + resource.region      
        elif resource.id.startswith("ocid1.autonomousdatabase"):
            redirectUrl = "https://cloud.oracle.com/db/adbs/" + resource.id +"?region=" + resource.region    
        elif resource.id.startswith("ocid1.odainstance"):
            redirectUrl = "https://cloud.oracle.com/digital-assistant/oda-instances/" + resource.id +"?region=" + resource.region
        elif resource.id.startswith("ocid1.analyticsinstance"):
            redirectUrl = "https://cloud.oracle.com/analytics/instances/" + resource.id +"?region=" + resource.region
        elif resource.id.startswith("ocid1.visualbuilderinstance"):
            redirectUrl = "https://cloud.oracle.com/vb/instances/" + resource.id +"?region=" + resource.region
        elif resource.id.startswith("ocid1.mysqldbsystem"):
            redirectUrl = "https://cloud.oracle.com/mysqlaas/db-systems/" + resource.id +"?region=" + resource.region
        elif resource.id.startswith("ocid1.integrationinstance"):
            redirectUrl = "https://cloud.oracle.com/oic/integration-instances/" + resource.id +"?region=" + resource.region
        elif resource.id.startswith("ocid1.datasciencenotebooksession"):
            redirectUrl = "https://cloud.oracle.com/data-science/notebook-sessions/" + resource.id +"?region=" + resource.region
        elif resource.id.startswith("ocid1.datasciencemodeldeployment"):
            redirectUrl = "https://cloud.oracle.com/data-science/model-deployments/" + resource.id +"?region=" + resource.region   
        elif resource.id.startswith("ocid1.disworkspace"):
            redirectUrl = "https://cloud.oracle.com/dis/" + resource.id +"/home?region=" + resource.region  
        elif resource.id.startswith("ocid1.goldengatedeployment"):
            redirectUrl = "https://cloud.oracle.com/goldengate/deployments/" + resource.id +"?region=" + resource.region              

        tbody += "\n  " 
        tbody += "\n  <!-- Instance-->"
        tbody += "\n  <tr>"
        tbody += "\n      <td style='height:24px' valign='bottom'>"
        tbody += "\n          <span style=\"height:24px; font-family:'Malgun Gothic','Oracle Sans','Oracle Sans Regular',Helvetica,Arial,sans-serif; font-style:normal; font-weight:400; font-size:14px; color:#161513\">"
        #tbody += "\n              &nbsp;&nbsp; " + resource.service_name + " | " + resource_name + " in " + resource.compartment_name
        tbody += "\n              &nbsp;&nbsp; [ " + resource.service_name + " ] &nbsp;"
        tbody += "                <a style='font-weight:500; color:#00688c; text-decoration: none; text-underline-offset:0.25m' target='_blank' href='" + redirectUrl + "'>"
        tbody +=                  resource_name + "</a>"        
        tbody +=                  " <i>in</i> " + resource.compartment_name
        tbody += "\n          </span>&nbsp;&nbsp;"
        #tbody += "\n          <span><a style=\"height:24px; font-family:'Malgun Gothic','Oracle Sans','Oracle Sans Regular',Helvetica,Arial,sans-serif; font-style:normal; font-weight:400; font-size:13.75px; color:#00688c\" target='_blank' href='" + redirectUrl + "'><i><u>OCI Console에서 자원 확인</u></i></a></span>"
        tbody += "\n      </td>"
        tbody += "\n  </tr>"

    title = "[" + signer.tenancy_name + "] " + "Nightly Stop"

    if hasattr(target_resources[0], 'name'):
        title += " - " + target_resources[0].name
    else:
        title += " - " + target_resources[0].display_name

    if configuration.language == "Korean":
        if (len(target_resources) > 1):
            title += " 등 총 " + str(len(target_resources)) + "개 일시 중지"
        else:
            title += " 일시 중지"        

        warningMessage = "Nightly Stop - 서비스 심야 절약 모드"
        if IS_FIRST_FRIDAY:
            warningMessage = "Nightly Stop - 오늘은 <b>이번달 첫번째 금요일!!</b> 예외 없이 모두 멈춤"
        main_message = signer.tenancy_name + " 테넌시 관리자가 설정한 Nightly Stop 자원 관리 정책에 따라, 스케줄러에 의해 아래 자원은 중지(Stop) 또는 비활성화(Deactivate) 되었습니다. <br>필요하신 시점에 시작(Start) 또는 활성화(Activate)하여 사용하시기 바랍니다."
    else:
        if (len(target_resources) > 1):
            title += ", along with " + str(len(target_resources)) + " others have been stopped"
        else:
            title += " has been stopped"        

        warningMessage = "Nightly Stop - Late-Night Cost Saving Mode"
        if IS_FIRST_FRIDAY:
            warningMessage = "Nightly Stop - Today is <b>the first Friday of the month!!</b> Everything stops — no exceptions."
        main_message = "As per the Nightly Stop resource management policy configured by the " + signer.tenancy_name + " tenancy administrator, the scheduler has stopped or deactivated the following resources. <br>You may start or activate them when needed."

    if configuration.language == "Korean":
        template = Path('mail-template/nightly_stop_notification_ko.html').read_text()
    else:
        template = Path('mail-template/nightly_stop_notification_en.html').read_text()

    html_body = template.replace("${title}", title)
    html_body = html_body.replace("${companyName}", signer.tenancy_name)
    html_body = html_body.replace("${headerImage}", "https://ci3.googleusercontent.com/meips/ADKq_NbPxsLyenwFfmz-f6Je7pVsAipkskSYJASeBzieNgGFsW0GYaHme6TCvbb6LDKTtN1E227iYqEXEmxtk_mFau2muY15hrzfcKjujIjdDJEA6OprriPEMzNBy0HM2u_-UYnp7JtczGEDhcxa73WiwAlWk6JSNkWpOJC8wYwSoZk2A1UnjMN9q4tk7YIvbgFJ2oxjEEGQvDRY3-fIuQFteTqWqQI=s0-d-e1-ft#https://idcs-545bcf5ba488439e82f6294f0fc978bb.identity.oraclecloud.com:443/ui/v1/public/common/asset/defaultBranding/oracle-email-header.png")
    html_body = html_body.replace("${warningMessage}", warningMessage)
    html_body = html_body.replace("${mainMessage}", main_message)
    html_body = html_body.replace("${tenancyName}", signer.tenancy_name)
    html_body = html_body.replace("${tbody}", tbody)

    send_email(configuration.sender_email, configuration.sender_name, to, configuration.cc, configuration.bcc, title, html_body)


def send_email(sender_email, sender_name, to, cc, bcc, subject, body):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = email.utils.formataddr((sender_name, sender_email))
    msg['To'] = to      # 'john.doe@example.com,john.smith@example.co.uk'
    recipients = to   

    if cc:
        msg['Cc'] = cc  # 'john.doe@example.com,john.smith@example.co.uk'
        recipients += ',' + cc

    if bcc:
        msg['Bcc'] = bcc  # 'john.doe@example.com,john.smith@example.co.uk'
        recipients += ',' + bcc        

    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP(configuration.smtp_host, configuration.smtp_port)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(configuration.smtp_username, configuration.smtp_password)
        server.sendmail(sender_email, recipients.split(','), msg.as_string())
        server.close()
    except Exception as ex:
        logging.error("ERROR: ", ex, flush=True)
    else:
        logging.info ("INFO: Email successfully sent!")


def is_first_friday_today():
    if configuration.enable_first_friday_all_stop.upper() != 'TRUE':
        return False

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
   
    first_day = datetime(today.year, today.month, 1).replace(hour=0, minute=0, second=0, microsecond=0)

    if first_day.weekday() <= 4:
        first_friday = first_day + timedelta(days=(4 - first_day.weekday()))
    else:
        first_friday = first_day + timedelta(days=(11 - first_day.weekday()))

    first_day_next_month = None
    if today.month < 12:
        first_day_next_month = datetime(today.year, today.month+1, 1).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        first_day_next_month = datetime(today.year+1, 1, 1).replace(hour=0, minute=0, second=0, microsecond=0)

    if first_day_next_month.weekday() <= 4:
        first_friday_next_month = first_day_next_month + timedelta(days=(4 - first_day_next_month.weekday()))
    else:
        first_friday_next_month = first_day_next_month + timedelta(days=(11 - first_day_next_month.weekday()))

    logging.info("                     Today: " + today.strftime("%Y-%m-%d %A"))
    logging.info("First Friday of This Month: " + first_friday.strftime("%Y-%m-%d %A"))
    logging.info("First Friday of Next Month: " + first_friday_next_month.strftime("%Y-%m-%d %A"))

    if today.weekday() != 4:  # 0: Monday, ..., 4: Friday
        return False
       
    if today == first_friday:
        return True
    else:
        return False    

IS_FIRST_FRIDAY = is_first_friday_today()
