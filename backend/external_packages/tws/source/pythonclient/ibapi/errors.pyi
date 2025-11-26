"""Type stubs for ibapi.errors module."""

class CodeMsgPair:
    errorCode: int
    errorMsg: str
    def __init__(self, code: int, msg: str) -> None: ...
    def code(self) -> int: ...
    def msg(self) -> str: ...

ALREADY_CONNECTED: CodeMsgPair
CONNECT_FAIL: CodeMsgPair
UPDATE_TWS: CodeMsgPair
NOT_CONNECTED: CodeMsgPair
UNKNOWN_ID: CodeMsgPair
UNSUPPORTED_VERSION: CodeMsgPair
BAD_LENGTH: CodeMsgPair
BAD_MESSAGE: CodeMsgPair
SOCKET_EXCEPTION: CodeMsgPair
FAIL_CREATE_SOCK: CodeMsgPair
SSL_FAIL: CodeMsgPair
INVALID_SYMBOL: CodeMsgPair
FA_PROFILE_NOT_SUPPORTED: CodeMsgPair
