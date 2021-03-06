#!/usr/bin/env python

from os import environ, path, system

from latigo.utils import load_yaml, save_yaml

pwd=path.dirname(path.realpath(__file__))

filename = pwd+"/local_config.yaml"

local_config = {}
failure = None


if not path.exists(filename):
    # Create a starting point for local config so that user can get quickly up
    # and running
    # fmt: off
    local_config={
        "LATIGO_MESSAGE": f"YOUR LOCAL ENV CAN NOW BE EDITED IN {filename}. RE-RUN THIS SCRIPT TO LOAD ANY CHANGES",
        "LATIGO_INTERNAL_EVENT_HUB": "GET YOUR EVENT_HUB CONNECTION STRING FROM AZURE PORTAL",
        "LATIGO_EXECUTOR_CONFIG_FILE": "THE LOCATION OF PREDICTION EXECUTOR CONFIG FILE IN YAML FORMAT",
        "LATIGO_SCHEDULER_CONFIG_FILE": "THE LOCATION OF PREDICTION SCHEDULER CONFIG FILE IN YAML FORMAT",
        "LATIGO_GORDO_RESOURCE": "The resource ID of gordo. Used for bearer authentication.",
        "LATIGO_GORDO_TENANT": "The  tenant latigo application in AD. Used for bearer authentication.",
        "LATIGO_GORDO_AUTH_HOST_URL": "The authority host URL. Used for bearer authentication.",
        "LATIGO_GORDO_CLIENT_ID": "The client ID of latigo aplication in AD. Used for bearer authentication.",
        "LATIGO_GORDO_CLIENT_SECRET": "The client secret of latigo aplication in AD. Used for bearer authentication.",
        "LATIGO_TIME_SERIES_RESOURCE": "The resource ID of time series api. Used for bearer authentication.",
        "LATIGO_TIME_SERIES_TENANT": "The tenant of time series api. Used for bearer authentication.",
        "LATIGO_TIME_SERIES_BASE_URL": "The base url of the time series api. This is what we create endpoint urls from when using the API.",
        "LATIGO_TIME_SERIES_AUTH_HOST_URL": "The authority host URL for time series api. Used for bearer authentication.",
        "LATIGO_TIME_SERIES_CLIENT_ID": "The client ID of time series api. Used for bearer authentication.",
        "LATIGO_TIME_SERIES_CLIENT_SECRET": "The client secret of time series api. Used for bearer authentication.",
    }
    # fmt: on
    
    save_yaml(filename, local_config)
else:
    local_config, failure = load_yaml(filename)

# from pprint import pprint; pprint(local_config)
if failure:
    print(f"Failed with {failure}")
else:
    for k, v in local_config.items():
        environ[k] = v
        system(f"export {k}={v}")
        print(f'export {k}="{v}"')
    print(f'export LATIGO_LOCAL_CONF_FILENAME="{filename}"')

