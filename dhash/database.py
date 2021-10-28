from __future__ import annotations

from typing import Tuple

from sqlalchemy import BigInteger, Column, Integer, String, UniqueConstraint

from database import database, session


class Hash(database.base):
    """Stored image hashes"""

    __tablename__ = "fun_dhash_hashes"

    idx = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger)
    channel_id = Column(BigInteger)
    message_id = Column(BigInteger)
    attachment_id = Column(BigInteger)
    hash = Column(String)

    __table_args__ = (
        UniqueConstraint(guild_id, channel_id),
        UniqueConstraint(message_id, attachment_id),
    )

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name} idx="{self.idx}" guild_id="{self.guild_id}" '
            f'channel_id="{self.channel_id}" message_id="{self.message_id}" '
            f'attachement_id="{self.attachment_id}" hash="{self.hash}">'
        )

    def dump(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "attachment_id": self.attachment_id,
            "hash": self.hash,
        }


class HashChannel(database.base):
    __tablename__ = "fun_dhash_channels"

    idx = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger)
    channel_id = Column(BigInteger)

    __table_args__ = (UniqueConstraint(guild_id, channel_id),)

    def add(guild_id: int, channel_id: int) -> HashChannel:
        channel = HashChannel(guild_id=guild_id, channel_id=channel_id)
        session.add(channel)
        session.commit()
        return channel

    def get(guild_id: int, channel_id: int) -> Optional[HashChannel]:
        query = (
            session.query(HashChannel)
            .filter_by(guild_id=guild_id, channel_id=channel_id)
            .one_or_none()
        )
        return query

    def get_all(guild_id: int) -> List[HashChannel]:
        query = session.query(HashChannel).filter_by(guild_id=guild_id).all()
        return query

    def remove(guild_id: int, channel_id):
        query = (
            session.query(HashChannel)
            .filter_by(guild_id=guild_id, channel_id=channel_id)
            .delete()
        )
        session.commit()
        return query

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__} idx="{self.idx}" '
            f'guild_id="{self.guild_id}" channel_id="{self.channel_id}">'
        )

    def dump(self) -> Dict[str, Union[int, str]]:
        return {
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
        }
