from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from aitrendigest.models import Base

_ENGINE_CACHE: dict[str, Engine] = {}


EngineTarget = str | Engine | sessionmaker[Session]


def _resolve_engine(target: EngineTarget) -> Engine:
    if isinstance(target, str):
        engine = _ENGINE_CACHE.get(target)
        if engine is None:
            engine = create_engine(target, future=True)
            _ENGINE_CACHE[target] = engine
        return engine
    if isinstance(target, Engine):
        return target

    engine = target.kw.get("bind")
    if isinstance(engine, Engine):
        return engine

    raise ValueError("session factory is not bound to an engine")


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = _resolve_engine(database_url)
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_schema(target: EngineTarget) -> None:
    engine = _resolve_engine(target)
    Base.metadata.create_all(engine)


def dispose_engine(database_url: str) -> None:
    engine = _ENGINE_CACHE.pop(database_url, None)
    if engine is not None:
        engine.dispose()
