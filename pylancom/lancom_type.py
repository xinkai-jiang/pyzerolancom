from enum import Enum
from typing import TypedDict

import zmq
import zmq.asyncio

IPAddress = str
Port = int
TopicName = str
ServiceName = str
AsyncSocket = zmq.asyncio.Socket
HashIdentifier = str

LANCOM_PUB = zmq.PUB
LANCOM_SUB = zmq.SUB
LANCOM_SRV = zmq.REQ


class NodeReqType(Enum):
    PING = "PING"
    NODE_INFO = "NODE_INFO"


class LanComMsg(Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    EMPTY = "EMPTY"


class SocketInfo(TypedDict):
    name: str
    socketID: HashIdentifier
    nodeID: HashIdentifier
    type: int
    ip: IPAddress
    port: Port


class NodeInfo(TypedDict):
    name: str
    nodeID: HashIdentifier
    infoID: int
    ip: IPAddress
    type: str
    pubList: list[SocketInfo]
    subList: list[SocketInfo]
    srvList: list[SocketInfo]
