from polyfactory.factories.pydantic_factory import ModelFactory

from trading_api.models.auth import DeviceInfo, RefreshTokenData, User, UserCreate


class UserFactory(ModelFactory[User]):
    """Factory for creating User model instances"""

    __model__ = User
    __check_model__ = True


class UserCreateFactory(ModelFactory[UserCreate]):
    """Factory for creating UserCreate model instances"""

    __model__ = UserCreate
    __check_model__ = True


class DeviceInfoFactory(ModelFactory[DeviceInfo]):
    """Factory for creating DeviceInfo model instances"""

    __model__ = DeviceInfo
    __check_model__ = True


class RefreshTokenDataFactory(ModelFactory[RefreshTokenData]):
    """Factory for creating RefreshTokenData model instances"""

    __model__ = RefreshTokenData
    __check_model__ = True
