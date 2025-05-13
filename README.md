# oci-nightly-stop
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/TheKoguryo/oci-nightly-stop/blob/master/README.md)
[![ko](https://img.shields.io/badge/lang-ko-blue.svg)](https://github.com/TheKoguryo/oci-nightly-stop/blob/master/README.ko.md)

Stop your OCI instances at night. And change the license models of your Databases and others to BYOL.

The original idea for this project was inspired by [oci-nigthly-stop](https://github.com/mmarukaw/oci-nigthly-stop). While the base concept was helpful, this repository includes a significantly restructured and expanded implementation with support for additional services.

## Supported Services for Stop
- Analytics Cloud
- Compute
- Data Integration
- Data Science
    * Notebook Sessions
    * Model Deployments
- Database
    * Base Database
    * Autonomous Database
- Digital Assistant
- GoldenGate
- HeatWave MySQL
- Oracle Integration 3
- Visual Builder

## Supported Services for Changing to BYOL 
- Analytics Cloud
- Database
    * Base Database
    * Autonomous Database
- GoldenGate  
- Oracle Integration 3


## Prerequisites
- [OCI SDK for Python](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/pythonsdk.htm#SDK_for_Python)
- Python 3.6 and above
    * [Supported Python Versions and Operating Systems](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/pythonsdk.htm#pythonsdk_topic-supported_python_versions__SupportedPythonVersionsandOperatingSystems)
- Pre-created oci-cli config file (~/.oci/config)
    * [OCI CLI Quickstart](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm)


## How to use

### How to add tag

1. Go to OCI Console.

2. Create Tag Namespaces in Root compartment

    - Namespace Definition Name: `Control`

3. Create Tag Key Definitions

    |Tag Key       |Description                             | Tag Value Type|Value                                                      |
    |--------------|----------------------------------------|---------------|-----------------------------------------------------------|
    |`Nightly-Stop`|If FALSE, does not stop at 24:00        | List          |`TRUE`<br> `FALSE`                                         |
    |`BYOL`        |If FALSE, does not change license model | List          |`TRUE`<br> `FALSE`                                         |
    |`Timezone`    |Compartment level tag                   | List          |`UTC+07:00`<br> `UTC+08:00`<br> `UTC+09:00`<br> `UTC+09:30`|

    - If you need, add more values in Timezone.

4. If you want to exclude instances from stopping, set defined tags below for individual compute and other instances.

    ![Control.Nightly-Stop: FALSE](images/tag_nightly-stop_false.png)

5. If you want to run nightly-stop at different times for each time zone, set defined tags - `Control.Timezone` for specific compartment.

    ![Control.Timezone: UTC+09:00](images/tag_timezone_in_compartment_level.png)

### How to run oci-nightly-stop

1. Create a Compute Instance.

    - Name: `oci-nightly-stop-vm` 

2. Install OCI CLI and configure the CLI in the created instance. And install OCI SDK for Python.

3. Clone this repository.

4. Open configuration.py file and set your enviroment values.

5. Run Example

    - Target:
    
        * all instances in the compartments that are tagged `Control.Timezone: UTC+09:00`

        ```$ run_nightly-stop.sh UTC+09:30 include```

    - Target: Except for those that are scheduled to run on other schedules.

        * all instances in the compartments that are no tagged `Control.Timezone`
        * all instances in the compartments that have other values, not `UTC+07:00`, `UTC+08:00`, `UTC+09:30` in `Control.Timezone`

        ```$ run_nightly-stop.sh UTC+07:00,UTC+08:00,UTC+09:30 exclude```

6. Use cron as your scheduler.

    - Run `crontab -e`

    - Create your schedules.

        ```
        ###############################################################################
        # Crontab to run oci-nightly-stop at 24:00 in each time zone
        ###############################################################################
        # UTC+09:30
        30 14 * * * timeout 1h /home/opc/oci-nightly-stop/run_nightly-stop.sh UTC+09:30 include >> /home/opc/oci-nightly-stop/run_nightly-stop.sh_run.txt_`date +\%Y\%m\%d-\%H\%M\%S` 2>&1 

        # UTC+09:00 - If a compartment does not have a timezone tag or is tagged with the remaining timezones, resources belonging to that compartment will be targeted.
        00 15 * * * timeout 1h /home/opc/oci-nightly-stop/run_nightly-stop.sh UTC+07:00,UTC+08:00,UTC+09:30 exclude >> /home/opc/oci-nightly-stop/run_nightly-stop.sh_run.txt_`date +\%Y\%m\%d-\%H\%M\%S` 2>&1
        
        # UTC+08:00
        00 16 * * * timeout 1h /home/opc/oci-nightly-stop/run_nightly-stop.sh UTC+08:00 include >> /home/opc/oci-nightly-stop/run_nightly-stop.sh_run.txt_`date +\%Y\%m\%d-\%H\%M\%S` 2>&1   
        
        # UTC+07:00
        00 17 * * * timeout 1h /home/opc/oci-nightly-stop/run_nightly-stop.sh UTC+07:00 include >> /home/opc/oci-nightly-stop/run_nightly-stop.sh_run.txt_`date +\%Y\%m\%d-\%H\%M\%S` 2>&1                 
       
        ```

### Required OCI IAM Policy

1. Create a dynamic group for the created Compute Instance

    - Name: `oci-nightly-stop-dg`

    - Rules:

        ```
        All {instance.id = 'the OCID of oci-nightly-stop-vm'}        
        ```            

2. Create a policy with following statements.

    - Name: `oci-nightly-stop-policy`

    - Rules:

        ```
        define tenancy usage-report as ocid1.tenancy.oc1..aaaaaaaaned4fkpkisbwjlr56u7cj63lf3wffbilvqknstgtvzub7vhqkggq
        endorse dynamic-group oci-nightly-stop-dg to read objects in tenancy usage-report
        Allow dynamic-group oci-nightly-stop-dg to inspect compartments in tenancy
        Allow dynamic-group oci-nightly-stop-dg to read usage-report in tenancy
        Allow dynamic-group oci-nightly-stop-dg to inspect domains in tenancy
        Allow dynamic-group oci-nightly-stop-dg to read analytics-instance in tenancy
        Allow dynamic-group oci-nightly-stop-dg to inspect db-systems in tenancy
        Allow dynamic-group oci-nightly-stop-dg to inspect db-nodes in tenancy
        Allow dynamic-group oci-nightly-stop-dg to inspect autonomous-databases in tenancy
        Allow dynamic-group oci-nightly-stop-dg to read instances in tenancy
        Allow dynamic-group oci-nightly-stop-dg to inspect dis-workspaces in tenancy
        Allow dynamic-group oci-nightly-stop-dg to inspect data-science-model-deployments in tenancy
        Allow dynamic-group oci-nightly-stop-dg to inspect data-science-notebook-sessions in tenancy
        Allow dynamic-group oci-nightly-stop-dg to inspect oda-instances in tenancy
        Allow dynamic-group oci-nightly-stop-dg to inspect goldengate-deployments in tenancy
        Allow dynamic-group oci-nightly-stop-dg to read integration-instance in tenancy
        Allow dynamic-group oci-nightly-stop-dg to read mysql-instances in tenancy
        Allow dynamic-group oci-nightly-stop-dg to read visualbuilder-instance in tenancy
        Allow dynamic-group oci-nightly-stop-dg to use analytics-instance in tenancy where request.operation = 'StopAnalyticsInstance'
        Allow dynamic-group oci-nightly-stop-dg to manage analytics-instance in tenancy where request.operation = 'UpdateAnalyticsInstance'
        Allow dynamic-group oci-nightly-stop-dg to manage db-nodes in tenancy where request.operation = 'DbNodeAction'
        Allow dynamic-group oci-nightly-stop-dg to manage db-systems in tenancy where request.operation = 'UpdateDbSystem'
        Allow dynamic-group oci-nightly-stop-dg to use autonomous-databases in tenancy where request.operation = 'StopAutonomousDatabase'
        Allow dynamic-group oci-nightly-stop-dg to use autonomous-databases in tenancy
        Allow dynamic-group oci-nightly-stop-dg to manage autonomous-databases in tenancy where request.operation = 'UpdateAutonomousDatabase'
        Allow dynamic-group oci-nightly-stop-dg to use instances in tenancy where request.operation = 'InstanceAction'
        Allow dynamic-group oci-nightly-stop-dg to manage dis-workspaces in tenancy where any {request.operation = 'StopWorkspace', request.operation = 'GetWorkspace'}
        Allow dynamic-group oci-nightly-stop-dg to manage data-science-model-deployments in tenancy where any {request.operation = 'DeactivateModelDeployment', request.operation = 'GetModelDeployment'}
        Allow dynamic-group oci-nightly-stop-dg to manage data-science-notebook-sessions in tenancy where any {request.operation = 'DeactivateNotebookSession', request.operation = 'GetNotebookSession'}
        Allow dynamic-group oci-nightly-stop-dg to use oda-instances in tenancy where any {request.operation = 'StopOdaInstance', request.operation = 'GetOdaInstance'}
        Allow dynamic-group oci-nightly-stop-dg to use goldengate-deployments in tenancy where request.operation = 'StopDeployment'
        Allow dynamic-group oci-nightly-stop-dg to use goldengate-deployments in tenancy where request.operation = 'UpdateDeployment'
        Allow dynamic-group oci-nightly-stop-dg to use goldengate-deployments in tenancy where request.operation = 'GetDeployment'
        Allow dynamic-group oci-nightly-stop-dg to use integration-instance in tenancy where request.operation = 'StopIntegrationInstance'
        Allow dynamic-group oci-nightly-stop-dg to use integration-instance in tenancy where request.operation = 'UpdateIntegrationInstance'
        Allow dynamic-group oci-nightly-stop-dg to use process-automation-instance in tenancy
        Allow dynamic-group oci-nightly-stop-dg to manage process-automation-instance in tenancy where request.operation = 'UpdateProcessInstances'
        Allow dynamic-group oci-nightly-stop-dg to manage process-automation-instance in tenancy where request.operation = 'UpdateProcessInstance'
        Allow dynamic-group oci-nightly-stop-dg to use mysql-instances in tenancy where request.operation = 'StopDbSystem'
        Allow dynamic-group oci-nightly-stop-dg to use visualbuilder-instance in tenancy where request.operation = 'StopVbInstance'
        Allow dynamic-group oci-nightly-stop-dg to inspect users in tenancy
        Allow dynamic-group oci-nightly-stop-dg to read clusters in tenancy where request.operation = 'GetCluster'
        Allow dynamic-group oci-nightly-stop-dg to read cluster-node-pools in tenancy where request.operation = 'GetNodePool'
        Allow dynamic-group oci-nightly-stop-dg to read desktop-pool in tenancy where request.operation = 'GetDesktopPool'   
        ```
