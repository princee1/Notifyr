from datetime import datetime, timedelta
from typing import Any, List, Optional, Self
from pyparsing import Literal
from redbeat.schedules import rrule
from celery.schedules import solar
from celery.schedules import crontab

from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator


def validate_clock_value(day,hour,minute,month,second,microsecond):

    if month is not None and (month < 1 or month > 12):
        raise ValueError("month must be between 1 and 12")
    if day is not None and (day < 1 or day > 31):
        raise ValueError("day must be between 1 and 31")
    if hour < 0 or hour > 23:
        raise ValueError("hour must be between 0 and 23")
    if minute < 0 or minute > 59:
        raise ValueError("minute must be between 0 and 59")
    if second < 0 or second > 59:
        raise ValueError("second must be between 0 and 59")
    if microsecond < 0 or microsecond > 999999:
        raise ValueError("microsecond must be between 0 and 999999")

class Scheduler(BaseModel):
    _object: Any = PrivateAttr(None)

    def build(self) -> Any:
        ...

class DateTimeSchedulerModel(Scheduler):
    year: int
    month: int | None = None
    day: int | None = None
    hour: int = 0
    minute: int = 0
    second: int = 0
    microsecond: int = 0
    tzinfo: str | None = None


    @model_validator(mode='after')
    def check_valid(self):
        validate_clock_value(self.day, self.hour, self.minute, self.month, self.second, self.microsecond)
        return self
    
    @model_validator(mode='after')
    def check_after(self) -> bool:
        self._object = self.build()
        if self._object < datetime.now(self.tzinfo):
            raise ValueError("Scheduled time must be in the future")
        return self

    def build(self) -> datetime:
        return datetime(
            year=self.year or datetime.now(self.tzinfo).year,
            month=self.month or 1,
            day=self.day or 1,
            hour=self.hour or 0,
            minute=self.minute or 0,
            second=self.second or 0,
            microsecond=self.microsecond or 0,
            tzinfo=self.tzinfo
        )

class TimedeltaSchedulerModel(Scheduler):
    days: int = 0
    seconds: int = 0
    microseconds: int = 0
    milliseconds: int = 0
    minutes: int = 0
    hours: int = 0
    weeks: int = 0 
   
    @model_validator(mode='after')
    def check_after(self) -> bool:
        self._object = self.build()
        if self._object.total_seconds() <= 0:
            raise ValueError("Timedelta must be positive")
        return self

    def build(self) -> timedelta:
        return timedelta(
            days=self.days,
            seconds=self.seconds,
            microseconds=self.microseconds,
            milliseconds=self.milliseconds,
            minutes=self.minutes,
            hours=self.hours,
            weeks=self.weeks,
        )     

class RRuleSchedulerModel(Scheduler):
    freq: Literal["YEARLY", "MONTHLY", "WEEKLY", "DAILY", "HOURLY", "MINUTELY", "SECONDLY"]
    interval: Optional[int] = Field(default=1, ge=1, description="Interval between each freq occurrence",le=100000000)

    bymonth: Optional[List[int]] = None
    bymonthday: Optional[List[int]] = None
    byweekday: Optional[List[int]] = None
    byhour: Optional[List[int]] = None
    byminute: Optional[List[int]] = None
    bysecond: Optional[List[int]] = None

    count: Optional[int] = Field(default=None, ge=1, description="Number of occurrences",le=100000000)
    until: Optional[DateTimeSchedulerModel] = None
    dtstart: Optional[DateTimeSchedulerModel] = None

    @field_validator("bymonth", each_item=True)
    def validate_month(cls, v):
        if not 1 <= v <= 12:
            raise ValueError("bymonth values must be between 1 and 12")
        return v

    @field_validator("bymonthday", each_item=True)
    def validate_monthday(cls, v):
        if not -31 <= v <= 31 or v == 0:
            raise ValueError("bymonthday must be between 1–31 or -31–-1")
        return v

    @field_validator("byweekday", each_item=True)
    def validate_weekday(cls, v):
        if not 0 <= v <= 6:
            raise ValueError("byweekday must be between 0 (Monday) and 6 (Sunday)")
        return v

    @field_validator("byhour", each_item=True)
    def validate_hour(cls, v):
        if not 0 <= v <= 23:
            raise ValueError("byhour must be between 0 and 23")
        return v

    @field_validator("byminute", each_item=True)
    def validate_minute(cls, v):
        if not 0 <= v <= 59:
            raise ValueError("byminute must be between 0 and 59")
        return v

    @field_validator("bysecond", each_item=True)
    def validate_second(cls, v):
        if not 0 <= v <= 59:
            raise ValueError("bysecond must be between 0 and 59")
        return v
    
    @model_validator(mode='after')
    def check_valid(self):
        if self.interval is not None and self.interval <= 0:
            raise ValueError("interval must be a positive integer")
        return self

    @model_validator(mode='after')
    def check_after(self:Self) -> Self:
        try:
            self._object = self.build()
        except Exception as e:
            raise ValueError("Invalid RRule configuration: " + str(e))
        return self

    def build(self) -> Any:
        return rrule(
            self.freq, dtstart=self.dtstart.build() if self.dtstart else None, until=self.until.build() if self.until else None,
            interval=self.interval, count=self.count,
            bymonth=self.bymonth, bymonthday=self.bymonthday, byweekday=self.byweekday,
            byhour=self.byhour, byminute=self.byminute, bysecond=self.bysecond
        )

class SolarSchedulerModel(Scheduler):
    event: Literal["sunrise", "sunset", "dawn", "dusk", "noon", "solar_noon"]
    latitude: float
    longitude: float
    offset: Optional[TimedeltaSchedulerModel] = None
    timezone: Optional[str] = None
    
    @model_validator(mode='after')
    def check_after(self):
        try:
            self._object = self.build()
        except Exception as e:
            raise ValueError("Invalid Solar configuration: " + str(e))
        return self

    def build(self) -> Any:
        if self.offset is None and self.timezone is None:
            return solar(self.event, self.latitude, self.longitude)
        return solar(self.event, self.latitude, self.longitude, offset=self.offset, timezone=self.timezone)

class CrontabSchedulerModel(BaseModel, Scheduler):
    minute: Optional[str] = '*'
    hour: Optional[str] = '*'
    day_of_week: Optional[str] = '*'
    day_of_month: Optional[str] = '*'
    month_of_year: Optional[str] = '*'
    year: Optional[str] = None
    timezone: Optional[str] = None

    @model_validator(mode='after')
    def check_after(self: Self) -> Self:
        try:
            self._object = self.build()
        except Exception as e:
            raise ValueError("Invalid Crontab configuration: " + str(e))
        return self

    def build(self) -> Any:
        # celery.schedules.crontab accepts None or string values for fields
        params = {
            'minute': self.minute,
            'hour': self.hour,
            'day_of_week': self.day_of_week,
            'day_of_month': self.day_of_month,
            'month_of_year': self.month_of_year,
            'year': self.year,
            'timezone': self.timezone,
        }
        # remove None keys because crontab() expects positional/keyword args that are meaningful only when provided
        return crontab(**{k: v for k, v in params.items() if v is not None})


