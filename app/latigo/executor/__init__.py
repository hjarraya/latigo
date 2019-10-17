from datetime import datetime
import time
import traceback
from os import environ
import pickle
import typing
import logging
import pprint
from latigo.sensor_data import Task, TimeRange, SensorData, PredictionData
from latigo.sensor_data.sensor_data import MockSensorDataProvider
from latigo.prediction.gordo import GordoPredictionExecutionProvider
from latigo.prediction import MockPredictionExecutionProvider, DevNullPredictionExecutionProvider
from latigo.prediction_storage import DevNullPredictionStorageProvider
from latigo.event_hub.receive import EventReceiveClient, EventConsumerClient


logger = logging.getLogger(__name__)


class PredictionExecutor:
    def _prepare_predictor(self):
        self.predictor_config = self.config.get("predictor", None)
        if not self.predictor_config:
            raise Exception("No predictor_config specified")
        predictor_type = self.predictor_config.get("type", None)
        self.name = self.predictor_config.get("name", "executor")
        self.predictor = None
        if "gordo" == predictor_type:
            self.predictor = GordoPredictionExecutionProvider(self.predictor_config)
        elif "mock" == predictor_type:
            self.predictor = MockPredictionExecutionProvider()
        elif "null" == predictor_type:
            self.predictor = DevNullPredictionExecutionProvider()

    def _prepare_sensor_data(self):
        pass

    def __init__(self, config: dict):
        if not config:
            raise Exception("No config specified")
        self.config = config
        self.do_async = self.config.get("do_async", False)
        self._prepare_predictor()
        if not self.predictor:
            raise Exception("No predictor configured, cannot continue...")
        self.in_connection_string = environ.get("LATIGO_INTERNAL_EVENT_HUB", None)
        print(f"PRED EXEC CON STR: {self.in_connection_string}")
        if not self.in_connection_string:
            raise Exception("No connection string specified for internal event hub. Please set environment variable LATIGO_INTERNAL_EVENT_HUB to valid connection string")
        self.sensor_data_provider = MockSensorDataProvider()
        connection_string = environ.get("LATIGO_INTERNAL_DATABASE", None)

        self.out_storage = DevNullPredictionStorageProvider(True)
        self.debug = False
        if not self.sensor_data_provider:
            raise Exception("No sensor data provider configured, cannot continue...")
        if not self.out_storage:
            raise Exception("No prediction store configured, cannot continue...")
        self.receiver = None
        self.consumer = None
        self.idle_time = datetime.now()
        self.idle_number = 0
        if self.do_async:
            self.consumer = EventConsumerClient(self.name, self.in_connection_string, self.debug)
        else:
            self.receiver = EventReceiveClient(self.name, self.in_connection_string, self.debug)
        if not self.receiver or not self.consumer:
            raise Exception("No task receiver or consumer configured")

    def _deserialize_task(self, task_bytes) -> typing.Optional[Task]:
        """
        Deserialize a task from bytes
        """
        task = None
        try:
            task = pickle.loads(task_bytes)
        except pickle.UnpicklingError as e:
            logger.error(f"Could not unpickle task of size {len(task_bytes)}bytes: {e}")
            traceback.print_exc()
        return task

    def _fetch_task(self) -> typing.Optional[Task]:
        """
        The task describes what the executor is supposed to do. This internal helper fetches one task from event hub
        """
        if not self.receiver:
            raise Exception("No task receiver configured")
        task = None
        try:
            task_bytes = self.receiver.receive_event_with_backoff()
            task = self._deserialize_task(task_bytes)
        except Exception as e:
            logger.error(f"Could not fetch task: {e}")
            traceback.print_exc()
        return task

    def _fetch_sensor_data(self, task: Task) -> typing.Optional[SensorData]:
        """
        Sensor data is input to prediction. This internal helper fetches one bulk of sensor data
        """
        sensor_data = None
        try:
            time_range = TimeRange(task.from_time, task.to_time)
            self.sensor_data_provider.get_data_for_range(time_range)
        except Exception as e:
            logger.error(f"Could not fetch sensor data for task {task}: {e}")
            traceback.print_exc()
        return sensor_data

    def _execute_prediction(self, task: Task, sensor_data: SensorData) -> typing.Optional[PredictionData]:
        """
        This internal helper executes prediction on one bulk of data
        """
        prediction_data = None
        try:
            prediction_data = self.predictor.execute_prediction("some_name", sensor_data)
        except Exception as e:
            logger.error(f"Could not execute prediction for task {task}: {e}")
            traceback.print_exc()
        return prediction_data

    def _store_prediction_data(self, task, prediction_data: PredictionData):
        """
        Prediction data represents the result of performing predictions on sensor data. This internal helper stores one bulk of prediction data to the store
        """
        try:
            self.out_storage.put_predictions(prediction_data)
        except Exception as e:
            logger.error(f"Could not store prediction data for task {task}: {e}")
            traceback.print_exc()

    def idle_count(self, has_task):
        if self.idle_number > 0:
            logger.info(f"Idle for {self.idle_number} cycles ({self.idle_time-datetime.now()})")
            self.idle_number = 0
            self.idle_time = datetime.now()
        else:
            self.idle_number += 1

    def run(self):
        if self.receiver:
            logger.info(f"Starting processing in {self.__class__.__name__}")
            done = False
            iteration_number = 0
            error_number = 0
            while not done:
                iteration_number += 1
                try:
                    task = self._fetch_task()
                    if task:
                        logger.info(f"Processing '{task}' for {self.__class__.__name__}")
                        sensor_data = self._fetch_sensor_data(task)
                        prediction_data = self._execute_prediction(task, sensor_data)
                        self._store_prediction_data(task, prediction_data)
                        self.idle_count(True)
                    else:
                        self.idle_count(False)
                        time.sleep(1)
                except Exception as e:
                    error_number += 1
                    logger.error("-----------------------------------")
                    logger.error(f"Error occurred in scheduler: {e}")
                    traceback.print_exc()
                    logger.error("")
                    time.sleep(1)
            logger.info(f"Stopping processing in {self.__class__.__name__}")
        else:
            logger.info(f"Skipping processing in {self.__class__.__name__}")

    def run_async(self):
        if self.consumer:
            logger.info(f"Starting async processing in {self.__class__.__name__}")
            done = False
            while not done:
                try:

                    def handle(data):
                        if data:
                            logger(f"Processing '{data}' for {self.__class__.__name__}")
                            data = f"Async Event '{data}'"
                            pd = PredictionData
                            pd.data = data
                            self.out_storage.put_predictions(pd)

                    self.consumer.consume_events(handle)
                except KeyboardInterrupt:
                    done = True
            logger.info(f"Stopping async processing in {self.__class__.__name__}")
        else:
            logger.info(f"Skipping async processing in {self.__class__.__name__}")
