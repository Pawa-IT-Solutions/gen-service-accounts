"""
The main aim of this file is to generate a service key for the user.
It has the following functions:
    1. Create the GCP project
    2. Enable the required APIs
    3. Create the service account
    4. Authorize the service account

Writes env variables to .env file
"""

import json
import base64
import requests
import logging
import urllib.parse
import google.auth.transport.requests
from google.auth import default
from google.cloud import service_usage_v1
from googleapiclient import discovery
from google.cloud import resourcemanager_v3
from googleapiclient.errors import HttpError


CLOUD_APIS = [
    "resourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "iam.googleapis.com"
]

APIS = [
    # If admin.googleapis.com is to be included, then it must be the first in this list.
    "admin.googleapis.com",
    "contacts.googleapis.com",
    "drive.googleapis.com",
    "gmail.googleapis.com",
    "serviceusage.googleapis.com",
    "iam.googleapis.com"
]

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/ndev.cloudman",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/admin.directory.orgunit.readonly",
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
    "https://www.googleapis.com/auth/admin.directory.group.readonly",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.settings.sharing",
    "https://www.googleapis.com/auth/directory.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/admin.directory.domain.readonly",
    "https://www.googleapis.com/auth/admin.directory.user",
    "https://www.googleapis.com/auth/admin.directory.group",
    "https://www.googleapis.com/auth/admin.datatransfer",
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/admin.reports.audit.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/ediscovery",
    "https://www.googleapis.com/auth/devstorage.full_control",
    "https://www.googleapis.com/auth/admin.reports.usage.readonly"
]



configs =  {
        "project_id":"test-project-1-321711",
        "CLIENT_SECRETS_FILE": "src/configs/credentials.json",
        "SCOPES": SCOPES,
        "APIS": APIS,
        "URL_FORMAT": (
            "https://admin.google.com/ac/owl/domainwidedelegation?"
            "overwriteClientId=true&clientIdToAdd={}&clientScopeToAdd={}&key={}"
        ),
        "TOOL_NAME": "pawait-drive-audit",
        "API_SERVICE_NAME": 'drive',
        "API_VERSION": 'v2',
        "BUCKET_NAME":"test-driveaudit-development-creds",
        "REDIRECT_URL": "https://0f37-197-232-61-226.in.ngrok.io/auth/oauth2callback"
    }


def search_organization(credentials,domain):
    client = resourcemanager_v3.OrganizationsClient(credentials=credentials)
    org = client.search_organizations(query=f"domain:{domain}")
    print(org)
    org_name = [i for i in org.pages]
    org_name = org_name[0].organizations[0].name

    # Specify the role you want to assign

    # Create a new IAM service object
    # iam_service = discovery.build('iam', 'v1', credentials=credentials)

    # Create a new request to add the service account and role to the organization
    
    # print(org_name)
    # Execute the request to add the service account and role to the organization
    # try:
    #     response = iam_service.organizations().setIamPolicy(resource=org_name, body=request).execute()
    # except Exception as e:
    #     print(e.args)

    # get the relevant permissions to get the required credentials

    return org_name


def authentcation()->dict:
    # authencate the user using various scopes
    auth_socpes = [
        "googleapis.com/auth/cloud-platform",
        "googleapis.com/auth/cloud-platform.read-only"
    ]
    creds,_ = default(scopes=auth_socpes)
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    return creds


def create_project(project_details:str):
    """Creates a new project.

    Args:
        project_name: The name of the project.
        project_id: The ID of the project.

    Returns:
        The project ID.
    """
    print("getting the organization")
    # organization = "organizations/1091352124180"
    # print(organization)
    print("Creating project...")
    
    client = resourcemanager_v3.ProjectsClient()
    request = resourcemanager_v3.CreateProjectRequest(
            project={"project_id": project_details,"display_name": project_details}
        )
    try:
        # Make the request
        operation = client.create_project(request=request)
        print("Waiting for operation to complete...")
        response = operation.result()
        print(response)

    except Exception as e:
        print(e.args)
        # print("Project already created. Getting the project")
        response = client.get_project(name=f"projects/{project_details}")

    # ! return a boolean value?
    print("%s successfully created \u2705", project_details)
    return "response"



# def try_enable_organization_apis(credentials):
#     org_id = "962006316057"
#     api = "resourcemanager.googleapis.com"
#     print("Enabling API...")
#     try:
#         client = service_usage_v1.ServiceUsageClient(credentials=credentials)
#         request = service_usage_v1.EnableServiceRequest(name=f"{api}")
#         operation = client.enable_service(request=request)
#         print("Waiting for operation to complete...")
#         operation.result()
#     except Exception as e:
#         print(e)

#     return True

def enable_apis(project_id):
    """Enables the required APIs.

    Args:
        project_id: The ID of the project.
    """
    print("Enabling APIs...")
    client = service_usage_v1.ServiceUsageClient()
    try:
        for api in configs["APIS"]:
            # Initialize request argument(s)
           
            request = service_usage_v1.EnableServiceRequest(name=f"projects/{project_id}/services/{api}")

            # Make the request
            operation = client.enable_service(request=request)
            print("Waiting for operation to complete...")
            operation.result()
    except Exception as e:
        print(e)

    print("APIs enabled \u2705")
    return "True"


def create_service_account(project_id:str)->dict:
    """Creates a service account.
    Args:
        project_id (str): The ID of the project.

    Returns:
        dict: The details of the service account that was created.
    """
    print("Creating service account...")
    service = discovery.build('iam', 'v1')
    service_account_name = "test-create-service-account"
    try:
        my_service_account = service.projects().serviceAccounts().create(
            name="projects/" + project_id,
            body={
                'accountId': f"{service_account_name}",
                'serviceAccount': {
                    'displayName': f"{service_account_name}"
                }
            }).execute()
        
    except HttpError as e:
        # print(e)
        my_service_account = service.projects().serviceAccounts().get(
            name=f"projects/{project_id}/serviceAccounts/{service_account_name}@{project_id}.iam.gserviceaccount.com",
        ).execute()

    service_account = {
        "email": my_service_account["email"],
        "name": my_service_account["name"],
        "unique_id": my_service_account["uniqueId"],
        "project_id": my_service_account["projectId"]
    }
    print("Service Account created \u2705")
    print("service Account details",service_account)
    return service_account

def get_auth_token(service_account_email: str, project_id: str):
    """Generate the auth token used by the admin user."""

    service = discovery.build('iam', 'v1')
    key =service.projects().serviceAccounts().keys().create(
        name=f"projects/{project_id}/serviceAccounts/{service_account_email}",
        body={
            'privateKeyType': 'TYPE_GOOGLE_CREDENTIALS_FILE',
            'keyAlgorithm': 'KEY_ALG_RSA_2048'
        }).execute()

    file_bytes = base64.b64decode(key["privateKeyData"])

    return file_bytes


def write_file_to_gcs(file_data, bucket_name, file_name):
    # writes using the google cloud run service account
    data = json.dumps({
        "file_data":file_data,
        "file_name":file_name,
        "bucket_name":bucket_name
    })
    url = "https://us-central1-test-driveaudit-development.cloudfunctions.net/function-2"
    request = requests.post(url,data=data)
    return request


def create_auth_url(service_account_unique_id):
    DWD_URL_FORMAT = """https://admin.google.com/ac/owl/domainwidedelegation?overwriteClientId=true&clientIdToAdd={}&clientScopeToAdd={}"""
    scopes = urllib.parse.quote(",".join(configs["SCOPES"]), safe="")
    authorize_url = DWD_URL_FORMAT.format(service_account_unique_id, scopes)
    return authorize_url

def write_file_to_local(file_data, file_name):
    with open(f".src/configs/{file_name}", "wb") as file:
        file.write(file_data)

def main(domain)->bool:
    """
    The main function which calls the above functions.
    """

    tool_name = f'{domain}-{configs["TOOL_NAME"].lower()}'

    project_details = f"{configs['TOOL_NAME'].lower()}"
    project_name = f"{configs['TOOL_NAME'].lower()}"


    bucket_name = configs["BUCKET_NAME"]
    file_name = f"{tool_name}-key.json"  # !file_name should be the domain of the user but for now we are using the project_details

    try:
 
        create_project(project_details)

        enable_apis(project_details)
        service_account = create_service_account(project_details)
        # file = get_auth_token(service_account["email"], project_id,creds)
        
        # write_file_to_gcs(file, bucket_name, file_name)
        # write_file_to_local(file, file_name)
        auth_url = create_auth_url(service_account["unique_id"])

        print("Service account key file created \u2705")
        return auth_url
    
    except Exception as e:
        print("Error",e)
        logging.error("Error occurred while creating the project \u274c")
        return "False"






if __name__ == "__main__":
   
   main(domain="reseller-test.cloudcompute.co.ke")

