from datetime import datetime, timedelta
from typing import Any, List, Optional, Self,Literal
from redbeat.schedules import rrule
from celery.schedules import solar
from celery.schedules import crontab
from celery.schedules import schedule


from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger



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
    _beat_object: Any = PrivateAttr(None)
    _aps_object: Any = PrivateAttr(None)


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
        
        datetime_obj = self.build()
        if datetime_obj < datetime.now(self.tzinfo):
            raise ValueError("Date time must be in the future")

        
        self._beat_object = self.build()
        self._aps_object = DateTrigger(self.build())

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
    days: int = Field(0,ge=0)
    seconds: int = Field(0,ge=0)
    microseconds: int = Field(0,ge=0)
    milliseconds: int = Field(0,ge=0)
    minutes: int = Field(0,ge=0)
    hours: int = Field(0,ge=0)
    weeks: int = Field(0,ge=0)
    tzinfo: str | None = None


    jitter: Optional[int] = Field(None,ge=0,le=9999)
    
    @model_validator(mode='after')
    def check_after(self) -> Self:
        _object = self.build('timedelta')
        if _object.total_seconds() <= 0:
            raise ValueError("Timedelta must be positive")

        self._beat_object = self.build(mode='datetime')
        
        self._aps_object = IntervalTrigger(
            self.weeks,self.days,self.hours,self.minutes,self.seconds,
            end_date=datetime.now() + _object + timedelta(seconds=30),
            timezone=self.tzinfo,
            jitter=self.jitter
        )
        return self

    def build(self,mode:Literal['datetime','timedelta']='datetime') -> datetime | timedelta:
        if mode == 'datetime':
            return datetime.now() + timedelta()
        
        return timedelta(
            days=self.days,
            seconds=self.seconds,
            microseconds=self.microseconds,
            milliseconds=self.milliseconds,
            minutes=self.minutes,
            hours=self.hours,
            weeks=self.weeks,
        )     

class IntervalSchedulerModel(Scheduler):
    interval:TimedeltaSchedulerModel
    relative:Optional[bool] =False
    start_date: Optional[DateTimeSchedulerModel] = None

    @model_validator(mode='after')
    def check_after(self)->Self:
        _obj = self.interval.build(mode='timedelta')

        self._beat_object = schedule(_obj,self.relative)
        self._aps_object = IntervalTrigger(
            self.interval.weeks,self.interval.days,self.interval.hours,self.interval.minutes,
            self.interval.seconds,end_date=None,jitter=self.interval.jitter,
            start_date=self.start_date.build()
        )

        return self

    def build(self):
        ...

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

    @staticmethod
    def clock_limit(name:str,v:list[int],a:int,b:int):
        if v is None:
            return v
        values = v if isinstance(v, (list, tuple, set)) else [v]
        for item in values:
            if not a <= item <= b:
                raise ValueError(f"{name} values must be between {a} and {b}")
        return v

    @field_validator("bymonth")
    def validate_bymonth(cls, v):
        return cls.clock_limit("bymonth",v,1,12)

    @field_validator("bymonthday")
    def validate_bymonthday(cls, v):
        return cls.clock_limit("bymonthday",v,1,31)

    @field_validator("byweekday")
    def validate_byweekday(cls, v):
        return cls.clock_limit("byweekday",v,0,6)

    @field_validator("byhour")
    def validate_byhour(cls, v):
        return cls.clock_limit("byhour",v,0,23)

    @field_validator("byminute")
    def validate_byminute(cls, v):
        return cls.clock_limit("byminute",v,0,59)

    @field_validator("bysecond")
    def validate_bysecond(cls, v):
        return cls.clock_limit("bysecond",v,0,59)


    @model_validator(mode='after')
    def check_valid(self):
        if self.interval is not None and self.interval <= 0:
            raise ValueError("interval must be a positive integer")
        return self

    @model_validator(mode='after')
    def check_after(self:Self) -> Self:
        try:
            self._beat_object = self.build()
        except Exception as e:
            raise ValueError("Invalid RRule configuration: " + str(e))
        return self

    def build(self) -> Any:
        return rrule(
            self.freq, dtstart=self.dtstart._beat_object if self.dtstart else None, until=self.until._beat_object if self.until else None,
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
    relative:Optional[bool] = False
    
    @model_validator(mode='after')
    def check_after(self):
        try:
            self._beat_object = self.build()
        except Exception as e:
            raise ValueError("Invalid Solar configuration: " + str(e))
        return self

    def build(self) -> Any:
        if self.offset is None and self.timezone is None:
            s= solar(self.event, self.latitude, self.longitude)
        else:
            s= solar(self.event, self.latitude, self.longitude, offset=self.offset.build('timedelta'), timezone=self.timezone)
        return schedule(s,self.relative)

class CrontabSchedulerModel(Scheduler):
    minute: Optional[str] = '*'
    hour: Optional[str] = '*'
    day_of_week: Optional[str] = '*'
    day_of_month: Optional[str] = '*'
    month_of_year: Optional[str] = '*'
    year: Optional[str] = None
    timezone: Optional[str] = None

    start_date:Optional[DateTimeSchedulerModel] = None
    end_date:Optional[DateTimeSchedulerModel] = None
    jitter:Optional[None] = Field(None,ge=0,le=9999)

    @model_validator(mode='after')
    def check_after(self: Self) -> Self:
        try:
            self._beat_object = self.build()
            self._aps_object = CronTrigger(day_of_week=self.day_of_week,minute=self.minute,
                day_of_week = self.day_of_week,month=self.month_of_year,year=self.year,
                start_date= None if self.start_date is None else self.start_date._beat_object,
                end_date= None if self.end_date is None else self.end_date._beat_object
            )
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


