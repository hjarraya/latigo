import pandas as pd
import typing
from datetime import datetime, timedelta
from collections import namedtuple
from dataclasses import dataclass
from dataclasses_json import dataclass_json, DataClassJsonMixin

from latigo.utils import rfc3339_from_datetime


@dataclass
class Task(DataClassJsonMixin):
    project_name: str = "unknown"
    model_name: str = "unknown"
    from_time: datetime = datetime.now() - timedelta(0, 20)
    to_time: datetime = datetime.now()


@dataclass
class TimeRange:

    from_time: datetime
    to_time: datetime

    def rfc3339_from(self):
        return rfc3339_from_datetime(self.from_time)

    def rfc3339_to(self):
        return rfc3339_from_datetime(self.to_time)

    def __str__(self):
        return f"TimeRange({self.from_time} -> {self.to_time})"


LatigoSensorTag = namedtuple("LatigoSensorTag", ["name", "asset"])


@dataclass
class SensorDataSpec:
    tag_list: typing.List[LatigoSensorTag]


@dataclass
class SensorData:

    time_range: TimeRange
    data: typing.Iterable[pd.Series]

    def __str__(self):
        return f"PredictionData({self.time_range})"


@dataclass
class PredictionData:
    name: str
    time_range: TimeRange
    data: typing.Iterable[typing.Tuple[str, pd.DataFrame, typing.List[str]]]

    def __str__(self):
        return f"PredictionData({self.time_range}, result={len(self.result)})"
