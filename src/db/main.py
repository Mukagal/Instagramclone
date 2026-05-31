from sqlmodel import text, SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from ..config import Config
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker

async_engine = create_async_engine(
    url=Config.DATABASE_URL,
    echo=True, 

    pool_pre_ping=True,
    pool_recycle=300,
)

async_session = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

async def initdb():
    """create a connection to our db"""

    async with async_engine.begin() as conn:
        #await conn.run_sync(SQLModel.metadata.create_all)
        statement = text("select 'Hello World'")

        result = await conn.execute(statement)

        print(result.all())

async def get_session(): 
    async with async_session() as session:
        yield session