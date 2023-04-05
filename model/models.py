from dataclasses import dataclass
from peewee import *
from typing import List, Optional
import datetime
import json


@dataclass
class PluginRunTimeOption(object):
    main: str


class BaseModel(Model):
    class Meta:
        database = SqliteDatabase("anno_class.db")


class Image(BaseModel):
    Path = CharField(unique=True)


class Annotation(BaseModel):
    Image = ForeignKeyField(Image, backref="annotations")
    VarType = TextField(unique=True)
    Value = TextField()


@dataclass
class DependencyModule:
    name: str
    version: str

    def __str__(self) -> str:
        return f'{self.name}=={self.version}'


@dataclass
class Variable:
    name: str
    vtype: type


@dataclass
class PluginConfig:
    name: str
    alias: str
    creator: str
    runtime: PluginRunTimeOption
    repository: str
    description: str
    version: str
    requirements: Optional[List[DependencyModule]]
    required_agents: Optional[List[str]]
    annotation_agent: bool


@dataclass
class Configuration:
    name: str
    vtype: type


@dataclass
class FilterPluginConfig:
    name: str
    alias: str
    creator: str
    runtime: PluginRunTimeOption
    repository: str
    description: str
    version: str
    requirements: Optional[List[DependencyModule]]
    annotation_agent: bool
    required_agents: Optional[List[str]]
    variables: Optional[List[Variable]]


class Collection(BaseModel):
    name = CharField(unique=True)
    description = TextField(null=True)
    createdAt = DateTimeField(default=datetime.datetime.now())
    deletedAt = DateTimeField(null=True)


class ImageInCollection(BaseModel):
    collection = ForeignKeyField(Collection, backref="images")
    image = ForeignKeyField(Image, backref="collectionImages")


class AnnotationAgent(BaseModel):
    name = CharField()
    alias = CharField(unique=True)
    creator = TextField()
    repository = TextField()
    description = TextField()
    version = TextField()


class AnnotationAct(BaseModel):
    name = TextField()
    value = TextField()
    valType = TextField()
    image = ForeignKeyField(Image, backref="annotations")
    agent = ForeignKeyField(AnnotationAgent, backref="annotations_act")


class FilterAgent(BaseModel):
    name = CharField()
    alias = CharField(unique=True)
    creator = TextField()
    repository = TextField()
    description = TextField()
    version = TextField()


class FilterAgentRequiredAnnotationAgent(BaseModel):
    filter_agent = ForeignKeyField(
        FilterAgent, backref="required_annotation_agents")
    annotation_agent = ForeignKeyField(
        AnnotationAgent, backref="required_by_filter_agents")


class FilterConfigAct(BaseModel):
    name = TextField()
    value = TextField()
    valType = TextField()


class FilterInstance(BaseModel):
    filter = ForeignKeyField(FilterAgent, backref="instances")
    configs = ForeignKeyField(FilterConfigAct, backref="filter_instance")
    position = IntegerField()


@dataclass
class ImageAnoCombo:
    path: str
    annotations: list[AnnotationAct]


@dataclass
class Meta:
    name: str
    description: str
    version: str

    def __str__(self) -> str:
        return f'{self.name}: {self.version}'
