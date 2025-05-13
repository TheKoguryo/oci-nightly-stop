########## Configuration ####################
# Specify your config file
configfile = '~/.oci/config'

# Specify your profile name
profile = 'default'

# Set TRUE if using instance principal signing
use_instance_principal = 'TRUE'

# Set TRUE if using Oracle internal tenancy for BYOL
is_internal_tenancy = 'FALSE'

# Set TRUE if using all stop feature on first friday of the month
enable_first_friday_all_stop = 'TRUE'

# Set top level compartment OCID. Tenancy OCID will be set if null.
# apackrsct
tenancy_id = 'ocid1.tenancy.oc1..xxx'
top_level_compartment_id = 'ocid1.tenancy.oc1..xxx'

# List compartment names to exclude
excluded_parent_compartments = ['ManagedCompartmentForPaaS', 'TEMP_COMPARTMENT_TO_BE_DELETED']
excluded_compartments = []

# List target regions. All regions will be counted if null.
target_region_names = []
excluded_region_names = []

# List resource ids to exclude
excluded_resource_ids = []
excluded_resource_ids.append('ocid1.autonomousdatabase.oc1.xxx')

# Set Email SMTP Server Info
enable_email_notification = 'TRUE'
smtp_username = "ocid1.user.oc1..xxx"
smtp_password = ""
smtp_host = "smtp.email.xxx.com"
smtp_port = "587"

# Set Email Sender Info
sender_email = "no-reply@xxx.xxx"
sender_name = "Nightly Stop"
cc = None
bcc = ""
language="Korean"
#language="English"
