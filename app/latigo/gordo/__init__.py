import typing
import random
import logging
import pprint
import numpy as np
import pandas as pd
import requests
import json
from datetime import datetime
import latigo.utils
from latigo.prediction_execution import PredictionExecutionProviderInterface

from latigo.types import TimeRange, SensorDataSpec, SensorData, PredictionData
from latigo.sensor_data import SensorDataProviderInterface

from latigo.model_info import ModelInfoProviderInterface
from latigo.auth import create_auth_session
from latigo.gordo.client import Client

# from gordo_components.client import Client
from gordo_components.data_provider.base import GordoBaseDataProvider, capture_args
from gordo_components.client.forwarders import PredictionForwarder
from gordo_components.dataset.sensor_tag import SensorTag


logger = logging.getLogger(__name__)
# logging.getLogger().setLevel(logging.WARNING)

gordo_client_instances_by_hash: dict = {}
gordo_client_instances_by_project: dict = {}
gordo_client_auth_session: typing.Optional[requests.Session] = None

# Defeat dependency on gordo
def _gordo_to_latigo_tag_list(gordo_tag_list):
    return gordo_tag_list


class LatigoDataProvider(GordoBaseDataProvider):
    """
    A GordoBaseDataProvider that wraps Latigo spesific data providers
    """

    @capture_args
    def __init__(self, sensor_data_provider: typing.Optional[SensorDataProviderInterface], config: dict):
        super().__init__()
        self.config = config
        if not self.config:
            raise Exception("No data_provider_config specified")
        self.sensor_data_provider = sensor_data_provider

    def load_series(self, from_ts: datetime, to_ts: datetime, tag_list: typing.List[SensorTag], dry_run: typing.Optional[bool] = False) -> typing.Iterable[pd.Series]:
        if self.sensor_data_provider:
            spec: SensorDataSpec = SensorDataSpec(tag_list=_gordo_to_latigo_tag_list(tag_list))
            time_range = TimeRange(from_ts, to_ts)
            sensor_data = self.sensor_data_provider.get_data_for_range(spec, time_range)
            if sensor_data and sensor_data.data:
                for item in sensor_data.data:
                    yield item

    def can_handle_tag(self, tag: SensorTag) -> bool:
        if self.sensor_data_provider:
            # TODO: Actually implement this
            return True
        return False


class LatigoPredictionForwarder(PredictionForwarder):
    """
    A Gordo PredictionForwarder that wraps Latigo spesific prediction forwarders
    """

    def __init__(self, prediction_storage, config):
        super().__init__()
        self.config = config
        if not self.config:
            raise Exception("No prediction_forwarder_config specified")
        self.prediction_storage = prediction_storage


def gordo_config_hash(config: dict):
    key = "gordo"
    parts = ["scheme", "host", "port", "project", "target", "gordo_version", "batch_size", "parallelism", "forward_resampled_sensors", "ignore_unhealthy_targets", "n_retries"]
    if config:
        for part in parts:
            key += part + config.get("scheme", "")
    return key


def clean_gordo_client_args(raw: dict):
    whitelist = ["project", "target", "host", "port", "scheme", "gordo_version", "metadata", "data_provider", "prediction_forwarder", "batch_size", "parallelism", "forward_resampled_sensors", "ignore_unhealthy_targets", "n_retries", "data_provider", "prediction_forwarder", "session"]
    args = {}
    for w in whitelist:
        args[w] = raw.get(w)
    # logger.info(pprint.pformat(raw))
    # logger.info(pprint.pformat(args))
    return args


def get_auth_session(auth_config: dict):
    global gordo_client_auth_session
    if not gordo_client_auth_session:
        # logger.info("CREATING SESSION:")
        gordo_client_auth_session = create_auth_session(auth_config)
    return gordo_client_auth_session


def allocate_gordo_client_instances(raw_config: dict):
    projects = raw_config.get("projects", [])
    auth_config = raw_config.get("auth", dict())
    session = get_auth_session(auth_config)
    if not isinstance(projects, list):
        projects = [projects]
    for project in projects:
        config = {**raw_config}
        config["project"] = project
        config["session"] = session
        key = gordo_config_hash(config)
        logger.info(f" + Instanciating Gordo Client: {key}")
        client = gordo_client_instances_by_hash.get(key, None)
        if not client:
            client = Client(**clean_gordo_client_args(config))
            gordo_client_instances_by_hash[key] = client
            gordo_client_instances_by_project[project] = client


def get_gordo_client_instance_by_project(project):
    return gordo_client_instances_by_project.get(project, None)


def _expand_gordo_connection_string(config: dict):
    if "connection_string" in config:
        connection_string = config.pop("connection_string")
        parts = latigo.utils.parse_gordo_connection_string(connection_string)
        if parts:
            config.update(parts)


class GordoPredictionExecutionProvider(PredictionExecutionProviderInterface):
    def __init__(self, sensor_data, prediction_storage, config):
        self.config = config
        if not self.config:
            raise Exception("No predictor_config specified")
        _expand_gordo_connection_string(self.config)
        # Augment config with the latigo data provider and prediction forwarders
        self.data_provider_config = config.get("data_provider", {})
        self.config["data_provider"] = LatigoDataProvider(sensor_data, self.data_provider_config)
        self.prediction_forwarder_config = config.get("prediction_forwarder", {})
        self.config["prediction_forwarder"] = LatigoPredictionForwarder(prediction_storage, self.prediction_forwarder_config)
        allocate_gordo_client_instances(config)

    def execute_prediction(self, project_name: str, model_name: str, sensor_data: SensorData) -> PredictionData:
        if not project_name:
            raise Exception("No project_name in gordo.execute_prediction()")
        if not model_name:
            raise Exception("No model_name in gordo.execute_prediction()")
        if not sensor_data:
            raise Exception("No sensor_data in gordo.execute_prediction()")
        client = get_gordo_client_instance_by_project(project_name)
        if not client:
            raise Exception("No client in gordo.execute_prediction()")
        result = client.predict(sensor_data.time_range.from_time, sensor_data.time_range.to_time)
        if not result:
            raise Exception("No result in gordo.execute_prediction()")
        return PredictionData(name=model_name, time_range=sensor_data.time_range, data=result)


class GordoModelInfoProvider(ModelInfoProviderInterface):
    def _prepare_auth(self):
        self.auth_config = self.config.get("auth")
        if not self.auth_config:
            raise Exception("No auth_config specified")

    def __init__(self, config):
        self.config = config
        if not self.config:
            raise Exception("No predictor_config specified")
        self._prepare_auth()
        _expand_gordo_connection_string(self.config)
        allocate_gordo_client_instances(config)

    def get_model_info(self, model_name: str):
        """
        Return any information about a named prediction
        """
        return {}

    def _normalize_to_models(self, projects_data):
        models = []
        for project_name, project_data in projects_data.items():
            for model_name, model_data in project_data.items():
                model_data["name"] = model_name
                model_data["project"] = project_name
                models.append(model_data)
        return models

    def get_models(self, filter: dict):
        """
        Return a list of predictions matching the given filter.
        """
        models = {}
        projects = filter.get("projects", [])
        # logger.info("Getting models for projects: ")
        # logger.info(pprint.pformat(projects))
        if not isinstance(projects, list):
            projects = [projects]
        for project in projects:
            # logger.info(f"LOOKING AT PROJECT {project}")
            client = get_gordo_client_instance_by_project(project)
            if client:
                meta_data = client.get_metadata()
                # logger.info(f" + FOUND METADATA for {project}: {len(meta_data)}")
                models[project] = meta_data
            else:
                logger.error(f" + NO CLIENT FOUND FOR PROJECT {project}")
        models = self._normalize_to_models(models)
        return models
