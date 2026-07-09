"""Dependency Injection для FastAPI."""

from src.engine.generator import DocumentGenerator
from src.engine.generator import generator as default_generator
from src.extractor.extractor import EntityExtractor
from src.extractor.extractor import extractor as default_extractor


def get_generator() -> DocumentGenerator:
    return default_generator


def get_extractor() -> EntityExtractor:
    return default_extractor
