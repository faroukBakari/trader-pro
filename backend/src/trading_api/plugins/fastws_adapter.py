from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

from fastapi import Depends, FastAPI

from external_packages.fastws.service import Client, FastWS

service = FastWS()


@service.send("ping", reply="ping")
async def send_event_a() -> None:
    return


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    service.setup(app)
    yield


app = FastAPI(lifespan=lifespan)


@app.websocket("/")
async def fastws_stream(client: Annotated[Client, Depends(service.manage)]) -> None:
    await service.serve(client)
    await service.serve(client)
